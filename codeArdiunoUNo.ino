#include <SD.h>
#include <Wire.h>
#include <Adafruit_INA219.h>

Adafruit_INA219 ina219;

const int chipSelect = 10;
const int ledPin = 3;
File myFile;

unsigned int lastFileNumber = 0;
unsigned long delayTime = 2500; 
char fileNameTxt[14] = ""; 
char dataStr[50] = ""; // کاهش سایز بافر
char buffer[10];      // افزایش سایز برای اعداد بزرگتر

void setup() 
{
    Serial.begin(115200);
    
    pinMode(ledPin, OUTPUT);
    digitalWrite(ledPin, LOW); 
    
    Serial.println(F("Starting up!"));

    if (!SD.begin(chipSelect)) {
        Serial.println(F("SD initialization failed!"));
        errorBlink();
    }
    else {
        Serial.println(F("SD card initialized."));
        
        File root = SD.open("/");
        lastFileNumber = getLastFileNumber(root);
        root.close();
        
        sprintf(fileNameTxt, "data%d.txt", lastFileNumber); 
        Serial.print(F("File: ")); Serial.println(fileNameTxt);
    }
    
    if (! ina219.begin()) {
        Serial.println(F("Failed to find INA219"));
        errorBlink();
    }
    Serial.println(F("INA219 initialized."));
}

void loop()
{   
    digitalWrite(ledPin, HIGH);


    dataStr[0] = '\0'; 
    float shuntvoltage = ina219.getShuntVoltage_mV();
    float busvoltage = ina219.getBusVoltage_V();
    float current_mA = ina219.getCurrent_mA();
    float power_mW = ina219.getPower_mW();
    float loadvoltage = busvoltage + (shuntvoltage / 1000);
    
    dtostrf(busvoltage, 5, 2, buffer);
    strcat(dataStr, buffer);
    strcat(dataStr, ",");

    dtostrf(shuntvoltage, 5, 2, buffer);
    strcat(dataStr, buffer);
    strcat(dataStr, ",");
    
    dtostrf(loadvoltage, 5, 2, buffer);
    strcat(dataStr, buffer);
    strcat(dataStr, ",");
    
    dtostrf(current_mA, 5, 2, buffer);
    strcat(dataStr, buffer);
    strcat(dataStr, ",");
    
    dtostrf(power_mW, 5, 2, buffer);
    strcat(dataStr, buffer);
    
    if (Serial) {
        Serial.print(F("Bus Voltage:   ")); Serial.print(busvoltage); Serial.println(F(" V"));
        Serial.print(F("Shunt Voltage: ")); Serial.print(shuntvoltage); Serial.println(F(" mV"));
        Serial.print(F("Load Voltage:  ")); Serial.print(loadvoltage); Serial.println(F(" V"));
        Serial.print(F("Current:       ")); Serial.print(current_mA); Serial.println(F(" mA"));
        Serial.print(F("Power:         ")); Serial.print(power_mW); Serial.println(F(" mW"));
        Serial.print(F("Data -> ")); Serial.println(dataStr);
    }

    writeToSD(dataStr);
    if(Serial){
        Serial.println(F("------------------------------"));
    }

    digitalWrite(ledPin, LOW);

    checkSerialCommand();
    sleepMode(delayTime);
}

void writeToSD(char* data) {
    myFile = SD.open(fileNameTxt, FILE_WRITE);
    if (myFile) {
        myFile.println(data);
        myFile.close();
        if (Serial) Serial.println(F("Write successful"));
    }
    else if (Serial) {
        Serial.println(F("Error opening file"));
    }
}

void sleepMode(unsigned long ms) {
    delay(ms);
}

void errorBlink() {
    while (1) {
        digitalWrite(ledPin, HIGH);
        delay(100);
        digitalWrite(ledPin, LOW);
        delay(200);

    }
}

int getLastFileNumber(File dir) {
    int maxNumber = 0;
    
    while (true) {
        File entry = dir.openNextFile();
        if (!entry) break;
        
        if (!entry.isDirectory()) {
            char name[13];
            strncpy(name, entry.name(), 12);
            name[12] = '\0';
            
            for(char *p = name; *p; p++) *p = tolower(*p);
            
            if (strncmp(name, "data", 4) == 0) {
                char *txtPos = strstr(name, ".txt");
                if (txtPos != NULL) {
                    int numLen = txtPos - (name + 4);
                    if (numLen > 0 && numLen <= 3) {
                        int number = atoi(name + 4);
                        if (number > maxNumber) maxNumber = number;
                    }
                }
            }
        }
        entry.close();
    }
    return maxNumber; 
}

void checkSerialCommand() {
    if(Serial.available()) {
        String inputString = Serial.readStringUntil('\n');
        inputString.trim();
        
        long newDelayTime = inputString.toInt();
        if (newDelayTime > 0) {
            delayTime = newDelayTime;
            if (Serial) {
                Serial.print(F("New delay: "));
                Serial.println(delayTime);
            }
        }
        else{
            if (inputString.equals("N")) {
                lastFileNumber++;
                // sampleNumber = 0;
                sprintf(fileNameTxt, "data%d.txt", lastFileNumber);
                if (Serial) {
                    Serial.print(F("New file: "));
                    Serial.println(fileNameTxt);
                }
            }
            else{
                if (inputString.equals("U")) {
                    bool  waitingForInput = true;
                    showAvailableDataFiles();
                    while (waitingForInput)
                    {
                        String input = Serial.readStringUntil('\n');
                        input.trim();
                        if (input.equals("q")) {
                            waitingForInput = false;
                        }
                        else{
                            if (input.length() > 0) {
                                int fileNumber = input.toInt();
                                char fileName[14];
                                sprintf(fileName, "data%d.txt", fileNumber);
                                sendFileOverSerial(fileName);
                            }
                        }
                    }
                }
            }
        }
    }
}

int freeRam() {
    extern int __heap_start, *__brkval;
    int v;
    return (int)&v - (__brkval == 0 ? (int)&__heap_start : (int)__brkval);
}


void showAvailableDataFiles() {
    Serial.println(F("Available data files:"));

    File root = SD.open("/");
    while (true) {
        File entry = root.openNextFile();
        if (!entry) break;
        
        if (!entry.isDirectory()) {
            String name = entry.name();
            name.toLowerCase();
            
            if (name.startsWith("data") && name.endsWith(".txt")) {
                Serial.println(name);
            }
        }
        entry.close();
    }
    root.close();
}


void sendFileOverSerial(const char* filename) {
    if (!SD.exists(filename)) {
        Serial.println(F("File not found."));
        return;
    }

    File file = SD.open(filename);
    if (!file) {
        Serial.println(F("Failed to open file."));
        return;
    }

    while (file.available()) {
        String line = file.readStringUntil('\n');
        line.trim(); 
        if (line.length() > 0) {
            Serial.println(line);
        }
    }
    file.close();
}
