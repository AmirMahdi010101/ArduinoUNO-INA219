#include <SD.h>

#include <Wire.h>
#include <Adafruit_INA219.h>

Adafruit_INA219 ina219;

const int chipSelect = 10;
File myFile;

unsigned long sampleNumber = 0; 
unsigned long delayTime = 2500; 
String fileNameTxt = ""; // File name to write data to
String dataStr = ""; 

void setup(void) 
{
    Serial.begin(115200);
    while (!Serial) {
        delay(10);
    }    

    Serial.println("Starting up!");

    Serial.print("Initializing SD card...  => ");
    
    if (!SD.begin(chipSelect)) {
        Serial.println("initialization failed!");
        while (1) {
            delay(10); 
        }
    }
    else
    {
        Serial.println("SD card initialized successfully.");
        
        File root = SD.open("/");
        int lastFileNumber = getLastFileNumber(root);
        root.close();
        
        fileNameTxt = "data" + String(lastFileNumber + 1) + ".txt"; // Increment file number
        Serial.print("File name: "); Serial.println(fileNameTxt);
    }
    
    // Initialize the INA219.
    if (! ina219.begin()) {
        Serial.println("Failed to find INA219 chip");
        while (1) {
            delay(10); 
        }
    }
    Serial.println("INA219 initialized successfully.");
}

void loop(void)
{   
    
    dataStr = "";
    float shuntvoltage = 0;
    float busvoltage = 0;
    float current_mA = 0;
    float loadvoltage = 0;
    float power_mW = 0;
    
    // Read data from INA219
    shuntvoltage = ina219.getShuntVoltage_mV();
    busvoltage = ina219.getBusVoltage_V();
    current_mA = ina219.getCurrent_mA();
    power_mW = ina219.getPower_mW();
    loadvoltage = busvoltage + (shuntvoltage / 1000);
    
    // Increment sample number
    sampleNumber++;
    
    //print data to Serial monitor
    Serial.print("Index: "); Serial.println(sampleNumber);
    Serial.print("Bus Voltage:   "); Serial.print(busvoltage); Serial.println(" V");
    Serial.print("Shunt Voltage: "); Serial.print(shuntvoltage); Serial.println(" mV");
    Serial.print("Load Voltage:  "); Serial.print(loadvoltage); Serial.println(" V");
    Serial.print("Current:       "); Serial.print(current_mA); Serial.println(" mA");
    Serial.print("Power:         "); Serial.print(power_mW); Serial.println(" mW");
    Serial.println("------------------------------");
    
    dataStr += String(sampleNumber) + ","; // Sample number
    dataStr += String(busvoltage) + ","; // Bus voltage
    dataStr += String(shuntvoltage) + ","; // Shunt voltage
    dataStr += String(loadvoltage) + ","; // Load voltage
    dataStr += String(current_mA) + ","; // Current
    dataStr += String(power_mW); // Power
    
    Serial.print("Data -> "); Serial.println(dataStr);
    
    // Open the file for writing
    myFile = SD.open(fileNameTxt, FILE_WRITE);
    if (myFile)
    {
        Serial.print("Writing to "); Serial.print(fileNameTxt); Serial.println("...");
        myFile.println(dataStr);
        myFile.close();
        Serial.println("Write successful");
    }
    else
    {
        Serial.println("Error opening");
    }
    delay(delayTime);

    checkSerialCommand();
}

void deleteFile()
{
    if (SD.exists(fileNameTxt)) 
    {
        SD.remove(fileNameTxt);
        if (Serial){
            Serial.print("Removing ->"); Serial.print(fileNameTxt);
            Serial.println("Done");
        }
    } 
}

int getLastFileNumber(File dir){
    int maxNumber = 0;
    
    while (true){
        File entry = dir.openNextFile();
        if (!entry) {
            break; // No more files
        }
        if (!entry.isDirectory()){
            String name = entry.name();

            name.toLowerCase();

            if (name.startsWith("data") && name.endsWith(".txt")){
                int startIdx = 4;
                int endIdx = name.indexOf(".txt");
                String numberStr = name.substring(startIdx, endIdx);
                int number = numberStr.toInt();
                if (number > maxNumber){
                    maxNumber = number;
                }
            }
        }
        entry.close();
    }
    return maxNumber;
}

void checkSerialCommand() {
    while (Serial.available()) {
        String inputString = "";
        inputString = Serial.readStringUntil('\n');
        inputString.trim(); 
        
        unsigned long newDelayTime = inputString.toInt();
        if (newDelayTime > 0) {
            delayTime = newDelayTime;
        }
    }
}