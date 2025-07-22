import sys
import serial
import serial.tools.list_ports
import csv
import os
import tempfile
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QTextEdit, QComboBox,QDialog,QTextBrowser,
    QPushButton, QCheckBox, QFileDialog, QLabel, QHBoxLayout, QLineEdit,
    QGroupBox, QGridLayout, QSplitter, QMessageBox, QMainWindow, QStatusBar,
    QToolBar, QAction,QShortcut
)
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QTimer
from PyQt5.QtGui import QTextCursor, QFont, QIcon, QKeySequence

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

class HelpWindow(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Help")
        # self.setModal(False)  # Make it non-modal
        self.setGeometry(100, 100, 800, 600)
        layout = QVBoxLayout()
        self.text_browser = QTextBrowser()
        self.text_browser.setOpenExternalLinks(True)
        layout.addWidget(self.text_browser)
        self.setLayout(layout)
        self.load_help_content()
        
    def show_centered(self, parent):
        parent_geo = parent.geometry()
        self.move(parent_geo.center() - self.rect().center())
        self.show()   
        
    def load_help_content(self):
        help_text = """
        <h1>📘 راهنمای استفاده از Serial Monitor</h1>

        <p>با استفاده از این برنامه، می‌توانید از طریق پورت سریال، دستورات مختلفی را به دستگاه ارسال کنید. دستورات به حروف کوچک و بزرگ حساس نیستند.</p>

        <h2>🛠️ دستورات قابل استفاده</h2>
        <table border="1" cellspacing="0" cellpadding="6">
            <tr style="background-color:#e0e0e0">
                <th>دستور</th>
                <th>توضیح</th>
                <th>مثال</th>
            </tr>
            <tr>
                <td><code>عدد مثبت</code></td>
                <td>تنظیم مدت زمان تاخیر (بر حسب میلی‌ثانیه)</td>
                <td><kbd>1000</kbd></td>
            </tr>
            <tr>
                <td><code>N</code></td>
                <td>ایجاد یک فایل جدید با شماره جدید</td>
                <td><kbd>N</kbd></td>
            </tr>
            <tr>
                <td><code>U</code></td>
                <td>نمایش لیست فایل‌ها و انتخاب فایل برای ارسال</td>
                <td><kbd>U</kbd></td>
            </tr>
            <tr>
                <td><code>Q</code></td>
                <td>خروج از حالت انتخاب فایل (بعد از U)</td>
                <td><kbd>Q</kbd></td>
            </tr>
        </table>

        <h2>📄 توضیحات بیشتر</h2>
        <ul>
            <li>برای تنظیم تاخیر، تنها کافی است یک عدد مثبت وارد کنید (مثلاً 500 یا 1000).</li>
            <li>با ارسال دستور <code>N</code>، فایل جدیدی با شماره افزایشی ذخیره می‌شود (مثلاً data3.txt).</li>
            <li>با دستور <code>U</code>، لیست فایل‌های موجود نمایش داده شده و می‌توانید با وارد کردن شماره فایل، آن را از طریق پورت سریال دریافت کنید.</li>
            <li>در حین انتخاب فایل (پس از <code>U</code>)، برای خروج از حالت انتخاب، دستور <code>Q</code> را وارد کنید.</li>
        </ul>

        <h2>💡 نکات</h2>
        <ul>
            <li>دستورات را می‌توانید با حروف بزرگ یا کوچک بنویسید؛ فرقی ندارد (مثلاً <code>n</code> یا <code>N</code>).</li>
            <li>پس از هر دستور، دکمه <kbd>Send</kbd> را فشار دهید.</li>
            <li>در صورت بروز خطا یا ارسال دستور ناصحیح، دستگاه ممکن است پاسخی ارسال نکند.</li>
        </ul>
        """
        self.text_browser.setHtml(help_text)   

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
        self.writer.writerow(["Index", "Relative time", "Bus Voltage(V)", "Shunt Voltage(mV)", "Load Voltage(V)", "Current(mA)", "Power(mW)"])
        self.data_count = 0
        
    def add_data(self, values):
        if isinstance(values, list):
            while len(values) < 5:
                values.append("")  
            
            self.writer.writerow(values[:5])
        else:
            try:
                if isinstance(values, str) and ',' in values:
                    parts = values.split(',')
                    while len(parts) < 5:
                        parts.append("")
                    self.writer.writerow(parts[:5])
                else:
                    self.writer.writerow([str(values)])
            except Exception as e:
                print(f"Error processing data in DataManager: {e}")
                self.writer.writerow([str(values)])
                
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
        
        self.is_waiting_for_files = False  
        self.file_list_received = False     
        self.is_receiving_file_data = False 
        self.selected_file_number = None    
        self.file_data_received = False     
        self.temp_file_manager = None       
        
        self.waiting_for_new_file = False
        self.new_file_received = False
        
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")
        
        self.init_ui()
        
        self.auto_save_timer = QTimer()
        self.auto_save_timer.timeout.connect(self.auto_save_data)
        self.auto_save_counter = 0
        
        self.file_data_timer = QTimer()
        self.file_data_timer.timeout.connect(self.check_file_data_completion)
        self.last_data_time = 0
        
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
        save_layout.addLayout(data_layout)
        
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

        help_action1 = QShortcut(QKeySequence("F2"), self)
        help_action1.activated.connect(self.show_help)
        help_action2 = QShortcut(QKeySequence("ctrl+h"), self)
        help_action2.activated.connect(self.show_help)

    def show_help(self):
        self.help_window = HelpWindow()
        self.help_window.show_centered(self)
        
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

        if self.waiting_for_new_file:
            if "New file:" in line:
                self.new_file_received = True
                self.waiting_for_new_file = False
                self.output_box.append(f"✅ {line}")
                if self.auto_scroll_checkbox.isChecked():
                    self.output_box.moveCursor(QTextCursor.End)
            return 
            
        if self.is_receiving_file_data:
            import time
            self.last_data_time = time.time()
            
            if self.temp_file_manager:
                self.temp_file_manager.add_data(line)
            
            if self.temp_file_manager.data_count % 10 == 0:  
                self.output_box.append(f"📊 Receiving data... ({self.temp_file_manager.data_count} points)")
                if self.auto_scroll_checkbox.isChecked():
                    self.output_box.moveCursor(QTextCursor.End)
            
            return
            
        elif self.is_waiting_for_files:
            if "Available data files:" in line:
                self.output_box.append("\n📁 --- AVAILABLE DATA FILES --- 📁")
                self.output_box.append(f"{line}")
                self.file_list_received = True
                
                self.output_box.append("\n👉 Please enter the file number you want to select.")
                self.output_box.append("👉 Send 'q' to return to normal mode when finished.\n")
                
                if self.auto_scroll_checkbox.isChecked():
                    self.output_box.moveCursor(QTextCursor.End)
                return
            
            elif self.file_list_received and any(f"[{i}]" in line for i in range(10)):
                self.output_box.append(f"{line}")
                if self.auto_scroll_checkbox.isChecked():
                    self.output_box.moveCursor(QTextCursor.End)
                return
            
            elif not self.file_list_received:
                return

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
                    self.plot_canvas.update_plot(values[0], values[1])  
                    self.status_bar.showMessage(f"Last values: BusVoltage={values[0]}, ShuntVoltage={values[1]}")
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

    def create_temp_file_manager(self, file_number):
        class TempFileManager:
            def __init__(self, file_number):
                self.file_number = file_number
                self.temp_file = tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.csv', encoding='utf-8', newline='')
                self.filename = self.temp_file.name
                self.writer = csv.writer(self.temp_file)
                self.writer.writerow(["Index", "Relative time", "Bus Voltage(V)", "Shunt Voltage(mV)", "Load Voltage(V)", "Current(mA)", "Power(mW)"])
                self.data_count = 0
                
            def add_data(self, data):
                try:
                    if ',' in data:
                        values = data.strip().split(',')
                        if len(values) >= 7:
                            self.writer.writerow(values[:7]) 
                        else:
                            while len(values) < 7:
                                values.append("")
                            self.writer.writerow(values)
                    else:
                        self.writer.writerow([data])
                    
                    self.temp_file.flush()
                    self.data_count += 1
                except Exception as e:
                    print(f"Error processing data: {e}")
                    self.writer.writerow([data])
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
        
        return TempFileManager(file_number)
    
    def check_file_data_completion(self):
        import time
        current_time = time.time()
        
        if self.is_receiving_file_data and (current_time - self.last_data_time > 3):
            self.file_data_timer.stop()
            self.output_box.append("\n✅ File data reception complete")
            self.output_box.append(f"📊 Received {self.temp_file_manager.data_count} data points")
            
            QTimer.singleShot(500, self.prompt_save_file_data)
            
            self.is_receiving_file_data = False
            self.file_data_received = True
    
    def prompt_save_file_data(self):
        if self.temp_file_manager and self.temp_file_manager.data_count > 0:
            filename, _ = QFileDialog.getSaveFileName(
                self, 
                f"Save File {self.selected_file_number} Data", 
                f"file_{self.selected_file_number}_data.csv", 
                "CSV Files (*.csv)"
            )
            
            if filename:
                try:
                    if self.temp_file_manager.save_to_file(filename):
                        self.output_box.append(f"✅ File data saved to: {filename}")
                        QMessageBox.information(self, "Save Successful", f"File {self.selected_file_number} data successfully saved to {filename}")
                except Exception as e:
                    self.output_box.append(f"❌ Error saving file data: {e}")
                    QMessageBox.critical(self, "Save Error", f"Error saving file data: {e}")
            else:
                self.output_box.append("❌ Save cancelled by user")
        
    def send_value(self):
        text = self.send_input.text().strip()
        if self.serial_thread and text:
            self.serial_thread.write_data(text)
            
            if text in ("U", "u") :
                self.clear_data()
                self.clear_console()
                self.output_box.append("✅ Command 'U' sent: Data and console cleared.")
                self.output_box.append("⏳ Waiting for available data files list...")
                self.is_waiting_for_files = True
                self.file_list_received = False
                self.is_receiving_file_data = False
                self.file_data_received = False
                self.selected_file_number = None
                
            elif text == "N":
                self.waiting_for_new_file = True
                self.clear_data()
                self.clear_console()
                self.output_box.append("✅ Command 'N' sent: Data and console cleared.")
                
            elif text == "q":
                if self.is_receiving_file_data and self.temp_file_manager and self.temp_file_manager.data_count > 0:
                    self.file_data_timer.stop()
                    self.prompt_save_file_data()
                
                self.clear_data()
                self.clear_console()
                self.output_box.append("✅ Command 'q' sent: Returning to normal mode.")
                self.is_waiting_for_files = False
                self.file_list_received = False
                self.is_receiving_file_data = False
                self.file_data_received = False
                self.selected_file_number = None
                self.file_data_timer.stop()
                
            else:
                if self.file_list_received and self.is_waiting_for_files and not self.is_receiving_file_data:
                    try:
                        file_number = int(text)
                        self.output_box.append(f"🔄 Sent file number: {file_number}")
                        self.selected_file_number = file_number
                        self.is_receiving_file_data = True
                        self.file_data_received = False
                        
                        self.temp_file_manager = self.create_temp_file_manager(file_number)
                        
                        import time
                        self.last_data_time = time.time()
                        self.file_data_timer.start(500)  
                        
                        self.output_box.append("⏳ Waiting for file data...")
                    except ValueError:
                        self.output_box.append(f"🔄 Sent: {text}")
                else:
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
    window.setWindowIcon(QIcon(r"icon/icon.ico"))
    window.show()
    sys.exit(app.exec_())