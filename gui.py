import sys
import serial
import serial.tools.list_ports
import csv
import os
import tempfile
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QTextEdit, QComboBox,
    QPushButton, QCheckBox, QFileDialog, QLabel, QHBoxLayout, QLineEdit,
    QGroupBox, QGridLayout, QSplitter, QMessageBox, QMainWindow, QStatusBar,
    QToolBar, QAction
)
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QTimer
from PyQt5.QtGui import QTextCursor, QFont, QIcon

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import numpy as np


class SerialReader(QThread):
    data_received = pyqtSignal(str)

    def __init__(self, port, baudrate=115200):
        super().__init__()
        self.port = port
        self.baudrate = baudrate
        self.running = False
        self.serial = None

    def run(self):
        self.running = True
        try:
            self.serial = serial.Serial(self.port, self.baudrate, timeout=1)
            while self.running:
                if self.serial.in_waiting > 0:
                    try:
                        line = self.serial.readline().decode('utf-8', errors='ignore').strip()
                        self.data_received.emit(line)
                    except Exception as e:
                        self.data_received.emit(f"Error reading: {e}")
        except Exception as e:
            self.data_received.emit(f"❌ Connection failed: {e}")

    def stop(self):
        self.running = False
        if self.serial and self.serial.is_open:
            self.serial.close()
        self.wait()

    def write_data(self, text):
        if self.serial and self.serial.is_open:
            try:
                self.serial.write(f"{text}\n".encode('utf-8'))
            except Exception as e:
                self.data_received.emit(f"❌ Error sending: {e}")


class LivePlotCanvas(FigureCanvas):
    def __init__(self, parent=None, max_points=100):
        fig = Figure(figsize=(5, 3), dpi=100)
        self.ax = fig.add_subplot(111)
        super().__init__(fig)
        self.setParent(parent)
        
        fig.set_facecolor('#f0f0f0')
        self.ax.set_facecolor('#f8f8f8')
        self.ax.grid(True, linestyle='--', alpha=0.7)
        
        title_font = {'fontsize': 6}
        label_font = {'fontsize': 6}
        tick_font = {'labelsize': 5}
        
        self.ax.set_title("BusVoltage and ShuntVoltage Plot", **title_font)
        self.ax.set_ylabel("Value", **label_font)
        self.ax.tick_params(**tick_font)

        self.max_points = max_points
        self.x_data = []
        self.y1_data = [] 
        self.y2_data = []  
        self.data_count = 0  

        self.line1, = self.ax.plot([], [], label="BusVoltage", color='#1f77b4', linewidth=1.5)
        self.line2, = self.ax.plot([], [], label="ShuntVoltage", color='#d62728', linewidth=1.5)
        self.ax.legend(prop={'size': 6})
        
        fig.tight_layout()

    def update_plot(self, new_y1, new_y2):
        try:
            new_y1 = float(new_y1)
            new_y2 = float(new_y2)
        except ValueError:
            return 

        self.data_count += 1
        
        if len(self.x_data) >= self.max_points:
            self.x_data.pop(0)
            self.y1_data.pop(0)
            self.y2_data.pop(0)
        
        self.x_data.append(self.data_count)
        self.y1_data.append(new_y1)
        self.y2_data.append(new_y2)

        self.line1.set_data(self.x_data, self.y1_data)
        self.line2.set_data(self.x_data, self.y2_data)
        
        x_min = self.data_count - self.max_points if self.data_count > self.max_points else 0
        self.ax.set_xlim(x_min, self.data_count)
        
        y_min = min(min(self.y1_data), min(self.y2_data)) * 0.9
        y_max = max(max(self.y1_data), max(self.y2_data)) * 1.1
        self.ax.set_ylim(y_min, y_max)
        
        self.draw()

    def clear_plot(self):
        self.x_data = []
        self.y1_data = []
        self.y2_data = []
        self.data_count = 0
        self.line1.set_data([], [])
        self.line2.set_data([], [])
        self.ax.relim()
        self.ax.autoscale_view()
        self.draw()


class DataManager:
    def __init__(self):
        self.temp_file = tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.csv', encoding='utf-8', newline='')
        self.filename = self.temp_file.name
        self.writer = csv.writer(self.temp_file)
        self.writer.writerow(["Index","Bus Voltage(V)", "Shunt Voltage(mV)", "Shunt Voltage(V)", "Current(mA)", "Power(mW)"])
        self.data_count = 0
        
    def add_data(self, values):
        self.writer.writerow(values)
        self.temp_file.flush()
        self.data_count += 1
        
    def save_to_file(self, target_filename):
        self.temp_file.close()
        
        with open(self.filename, 'r', newline='') as src_file:
            with open(target_filename, 'w', newline='') as dst_file:
                dst_file.write(src_file.read())
        
        return True
        
    def __del__(self):
        if hasattr(self, 'temp_file') and self.temp_file:
            self.temp_file.close()
            try:
                os.unlink(self.filename)
            except:
                pass


class SerialMonitor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Serial Monitor")
        self.resize(800, 750)
        self.serial_thread = None
        self.data_manager = None
        self.max_display_lines = 500

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")
        
        self.init_ui()
        
        self.auto_save_timer = QTimer()
        self.auto_save_timer.timeout.connect(self.auto_save_data)
        self.auto_save_counter = 0
        
    def init_ui(self):
        main_layout = QVBoxLayout(self.central_widget)
        
        top_section = QHBoxLayout()
        
        port_group = QGroupBox("Serial Connection")
        port_layout = QGridLayout()
        port_group.setLayout(port_layout)
        
        port_layout.addWidget(QLabel("Port:"), 0, 0)
        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(200)
        port_layout.addWidget(self.port_combo, 0, 1)
        
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh_ports)
        port_layout.addWidget(self.refresh_btn, 0, 2)
        
        port_layout.addWidget(QLabel("Baudrate:"), 1, 0)
        self.baudrate_combo = QComboBox()
        self.baudrate_combo.addItems(["9600", "19200", "38400", "57600", "115200"])
        self.baudrate_combo.setCurrentText("115200")
        port_layout.addWidget(self.baudrate_combo, 1, 1)
        
        connection_layout = QHBoxLayout()
        self.start_btn = QPushButton("Connect")
        self.stop_btn = QPushButton("Disconnect")
        self.start_btn.clicked.connect(self.start_reading)
        self.stop_btn.clicked.connect(self.stop_reading)
        connection_layout.addWidget(self.start_btn)
        connection_layout.addWidget(self.stop_btn)
        port_layout.addLayout(connection_layout, 1, 2)
        
        top_section.addWidget(port_group)
        
        save_group = QGroupBox("Data Management")
        save_layout = QVBoxLayout()
        save_group.setLayout(save_layout)
        
        data_layout = QHBoxLayout()
        
        self.auto_save_checkbox = QCheckBox("Auto-save every 100 points")
        self.auto_save_checkbox.setChecked(True)
        # data_layout.addWidget(self.auto_save_checkbox)
        
        save_layout.addLayout(data_layout)
        
        # Save buttons  
        save_buttons_layout = QHBoxLayout()
        self.save_btn = QPushButton("Save to CSV")
        self.save_btn.clicked.connect(self.save_to_csv)
        save_buttons_layout.addWidget(self.save_btn)
        
        self.clear_data_btn = QPushButton("Clear Data")
        self.clear_data_btn.clicked.connect(self.clear_data)
        save_buttons_layout.addWidget(self.clear_data_btn)
        
        save_layout.addLayout(save_buttons_layout)
        
        send_layout = QHBoxLayout()
        self.send_input = QLineEdit()
        self.send_input.setPlaceholderText("Enter value to send")
        self.send_btn = QPushButton("Send")
        self.send_btn.clicked.connect(self.send_value)
        send_layout.addWidget(QLabel("Value:"))
        send_layout.addWidget(self.send_input)
        send_layout.addWidget(self.send_btn)
        save_layout.addLayout(send_layout)
        
        top_section.addWidget(save_group)
        
        main_layout.addLayout(top_section)
        
        
        splitter = QSplitter(Qt.Vertical)
        main_layout.addWidget(splitter, 1)
        
        console_widget = QWidget()
        console_layout = QVBoxLayout(console_widget)
        
        console_group = QGroupBox("Serial Console")
        console_inner_layout = QVBoxLayout()
        console_group.setLayout(console_inner_layout)
        
        scroll_layout = QHBoxLayout()
        self.auto_scroll_checkbox = QCheckBox("Auto-scroll")
        self.auto_scroll_checkbox.setChecked(True)
        scroll_layout.addWidget(self.auto_scroll_checkbox)
        
        self.clear_btn = QPushButton("Clear Console")
        self.clear_btn.clicked.connect(self.clear_console)
        scroll_layout.addWidget(self.clear_btn)
        
        scroll_layout.addStretch()
        
        console_inner_layout.addLayout(scroll_layout)
        
        self.output_box = QTextEdit()
        self.output_box.setReadOnly(True)
        self.output_box.setFont(QFont("Consolas", 10))
        console_inner_layout.addWidget(self.output_box)
        
        console_layout.addWidget(console_group)
        
        splitter.addWidget(console_widget)
        
        plot_widget = QWidget()
        plot_layout = QVBoxLayout(plot_widget)
        
        plot_group = QGroupBox("Live Data Plot")
        plot_inner_layout = QVBoxLayout()
        plot_group.setLayout(plot_inner_layout)
        
        plot_options = QHBoxLayout()
        self.plot_points_label = QLabel("Visible points:")
        plot_options.addWidget(self.plot_points_label)
        
        self.plot_points_combo = QComboBox()
        self.plot_points_combo.addItems(["50", "100", "200", "500", "1000"])
        self.plot_points_combo.setCurrentText("100")
        self.plot_points_combo.currentTextChanged.connect(self.change_plot_size)
        plot_options.addWidget(self.plot_points_combo)
        
        plot_inner_layout.addLayout(plot_options)
        
        self.plot_canvas = LivePlotCanvas(max_points=int(self.plot_points_combo.currentText()))
        plot_inner_layout.addWidget(self.plot_canvas)
        
        plot_layout.addWidget(plot_group)
        
        splitter.addWidget(plot_widget)
        
        self.refresh_ports()
        
        splitter.setSizes([350, 250])
        
        self.stop_btn.setEnabled(False)

    def refresh_ports(self):
        self.port_combo.clear()
        ports = serial.tools.list_ports.comports()
        ch340_ports = [p for p in ports if "CH340" in p.description]
        other_ports = [p for p in ports if "CH340" not in p.description]
        sorted_ports = ch340_ports + other_ports
        
        if not sorted_ports:
            self.port_combo.addItem("No ports available")
            self.status_bar.showMessage("No serial ports found")
            return
            
        for port in sorted_ports:
            self.port_combo.addItem(f"{port.device} - {port.description}", port.device)
        
        if ch340_ports:
            self.port_combo.setCurrentIndex(0)
            
        self.status_bar.showMessage(f"Found {len(sorted_ports)} port(s)")

    def start_reading(self):
        selected_port = self.port_combo.currentData()
        if not selected_port:
            self.output_box.append("Please select a port.")
            self.status_bar.showMessage("No port selected")
            return

        baudrate = int(self.baudrate_combo.currentText())
        self.serial_thread = SerialReader(selected_port, baudrate)
        self.serial_thread.data_received.connect(self.handle_data)
        self.serial_thread.start()
        
        self.data_manager = DataManager()
        
        self.output_box.append(f"✅ Connected to {selected_port} at {baudrate} baud.")
        self.output_box.append(f"✅ Temporary file created: {self.data_manager.filename}")
        self.status_bar.showMessage(f"Connected to {selected_port}")
        
        if self.auto_save_checkbox.isChecked():
            self.auto_save_timer.start(1000)  
        
        self.start_btn.setEnabled(False)
        self.port_combo.setEnabled(False)
        self.baudrate_combo.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.plot_canvas.clear_plot()

    def stop_reading(self):
        if self.serial_thread:
            self.serial_thread.stop()
            self.serial_thread = None
            self.output_box.append("⏹ Connection closed.")
            self.status_bar.showMessage("Disconnected")
            
            self.auto_save_timer.stop()
            
            self.start_btn.setEnabled(True)
            self.port_combo.setEnabled(True)
            self.baudrate_combo.setEnabled(True)
            self.stop_btn.setEnabled(False)

    def handle_data(self, line):
        if self.output_box.document().lineCount() > self.max_display_lines:
            cursor = self.output_box.textCursor()
            cursor.movePosition(QTextCursor.Start)
            cursor.movePosition(QTextCursor.Down, QTextCursor.KeepAnchor, 100)
            cursor.removeSelectedText()

        self.output_box.append(f"{line}")
        if self.auto_scroll_checkbox.isChecked():
            self.output_box.moveCursor(QTextCursor.End)

        if "Data ->" in line:
            try:
                parts = line.split("Data ->")[-1].strip()
                values = parts.split(",")
                
                if self.data_manager:
                    self.data_manager.add_data(values)
                    
                    if self.auto_save_checkbox.isChecked():
                        self.auto_save_counter = self.data_manager.data_count

                if len(values) >= 5:
                    self.plot_canvas.update_plot(values[3], values[4])  
                    self.status_bar.showMessage(f"Last values: BusVoltage={values[3]}, ShuntVoltage={values[4]}")
            except Exception as e:
                self.output_box.append(f"Error processing data: {e}")

    def clear_console(self):
        self.output_box.clear()
        
    def clear_data(self):
        if self.data_manager:
            old_manager = self.data_manager
            self.data_manager = DataManager()
            del old_manager 
            
            self.plot_canvas.clear_plot()
            self.output_box.append("✅ Data cleared and plot reset.")
            
            self.auto_save_counter = 0

    def change_plot_size(self, value):
        try:
            max_points = int(value)
            self.plot_canvas.max_points = max_points
            self.output_box.append(f"✅ Plot size changed to {max_points} points.")
        except ValueError:
            pass

    def auto_save_data(self):
        if self.data_manager and self.auto_save_checkbox.isChecked():
            data_diff = self.data_manager.data_count - self.auto_save_counter
            if data_diff >= 100:
                try:
                    auto_save_dir = os.path.join(os.path.expanduser("~"), "SerialMonitor_AutoSave")
                    if not os.path.exists(auto_save_dir):
                        os.makedirs(auto_save_dir)
                        
                    import datetime
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = os.path.join(auto_save_dir, f"auto_save_{timestamp}.csv")
                    
                    self.data_manager.save_to_file(filename)
                    
                    self.output_box.append(f"🔄 Auto-saved data to {filename}")
                    self.auto_save_counter = self.data_manager.data_count
                except Exception as e:
                    self.output_box.append(f"Auto-save failed: {e}")

    def save_to_csv(self):
        if not self.data_manager or self.data_manager.data_count == 0:
            self.output_box.append("No data available to save.")
            QMessageBox.warning(self, "Save Data", "No data available to save.")
            return

        filename, _ = QFileDialog.getSaveFileName(self, "Save File", "data.csv", "CSV Files (*.csv)")
        if filename:
            try:
                if self.data_manager.save_to_file(filename):
                    self.output_box.append(f"✅ File saved: {filename}")
                    QMessageBox.information(self, "Save Successful", f"Data successfully saved to {filename}")
            except Exception as e:
                self.output_box.append(f"❌ Error saving file: {e}")
                QMessageBox.critical(self, "Save Error", f"Error saving file: {e}")

    def send_value(self):
        text = self.send_input.text().strip()
        if self.serial_thread and text:
            self.serial_thread.write_data(text)
            self.output_box.append(f"🔄 Sent: {text}")
            self.send_input.clear()
        else:
            if not self.serial_thread:
                self.output_box.append("Not connected to a serial port.")
            elif not text:
                self.output_box.append("Please enter a value to send.")

    def closeEvent(self, event):
        try:
            self.stop_reading()

            if self.data_manager and self.data_manager.data_count > 0:
                reply = QMessageBox.question(
                    self,
                    "Exit Application?",
                    QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                    QMessageBox.Save
                )

                if reply == QMessageBox.Save:
                    self.save_to_csv()
                    event.accept()
                elif reply == QMessageBox.Discard:
                    event.accept()
                else:
                    event.ignore()
            else:
                reply = QMessageBox.question(
                    self,
                    "Exit Application?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                if reply == QMessageBox.Yes:
                    event.accept()
                else:
                    event.ignore()
        except Exception as e:
            self.stop_reading()
            event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = SerialMonitor()
    window.show()
    sys.exit(app.exec_())