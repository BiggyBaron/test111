#!/usr/bin/env python3

import sh
import sys
import copy
import time
import logging
import datetime
import pandas as pd


now = datetime.datetime.now()
logging.basicConfig(level=logging.INFO,format='%(asctime)s: %(message)s')


class Hack:
    def __init__(self):
        logging.info('Hack is initialized')
        self.state = False
        self.status = False
        self.period = 10
        self.times = 0
        self.bases = []
        self.data = False
        self.imsis = []
        self.neighbours = []
        
    def scanner(self):
        self.bases = []
        self.stopLive()
        if self.check_blade():
            logging.info("Blade is connected")
            self.state = True
        else:
            logging.info("Blade is not connected")
            self.state = False
            return 0
        scan = sh.Command("grgsm_scanner")
        raw_out = scan(_bg=True)
        logging.info('Started scanning')
        raw_out.wait()
        logging.info("Scanning is finished, parsing:")
        btss = []
        for line in raw_out:
            if line[0] == "A":
                arfcn = int(line.split("ARFCN:")[1].split(",")[0])
                freq = line.split("Freq:  ")[1].split(",")[0]
                bts1 = {"ARFCN": arfcn, "FREQ": freq}
                btss.append(copy.deepcopy(bts1))
        for el in btss:
            logging.info(el)
        
        self.bases = btss

    def detect_cell(self, imsi):
        cell = imsi[3:5]

        if cell == "01":
            vendor = "Beeline"
        elif cell == "02":
            vendor = "Kcell"
        elif cell == "77":
            vendor = "Tele-2"
        elif cell == "07":
            vendor = "Altel"
        else:
            vendor = "Kazakhtelekom other"
        
        return vendor

    def process_output(self, line):
        if "2b" in line and self.data == False:
            self.data = True
    
    def catch_imsi(self, hours):
        self.imsis = []
        self.period = float(hours)*3600/len(self.bases)
        logging.info("Started listen with period = " + str(self.period))
        cmd_main = "grgsm_livemon_headless"
        for el in self.bases:
            freq = str(el["FREQ"])
            logging.info("Starting: " + cmd_main + " -f " + freq)
            listen = sh.Command(cmd_main)
            self.data = False

            done = False
            while done == False:
                try:
                    bytes = listen("-f", freq, _out=self.process_output, _bg=True, _bg_exc=False)
                    time.sleep(10)
                    done = True
                except:
                    logging.error("livemon is up already: killing")
                    self.stopLive()
                    time.sleep(2)
            if self.data == True:
                logging.info("There is data from bts.")
                new_bs = {}
                catch = sh.Command("tshark")
                logging.info("Starting tshark to capture.")
                imsis = catch("-i", "lo", "-Y", "e212.imsi", "-T", "fields", "-e", "e212.imsi",
                    "-e", "frame.time", "-a", "duration:" + str(self.period), _bg=True)
                imsis.wait()
                self.stopLive()
                for imsi in imsis:
                    if "401" in str(imsi):
                        new_bs["imsi"] = str(imsi).split("\t")[0]
                        new_bs["time"] = str(imsi).split("\t")[1].split("\n")[0]
                        new_bs["ARFCN"] = el["ARFCN"]
                        new_bs["Vendor"] = self.detect_cell(str(imsi))
                        self.imsis.append(copy.deepcopy(new_bs))
                        new_bs = {}
                        logging.info("Found IMSI: " + str(imsi).split("\t")[0])
            else:
                logging.info("There is no data from bts.")
                
            self.stopLive()
        
        df = pd.DataFrame.from_dict(self.imsis)
        df.to_excel('imsis.xlsx')
    
    def check_blade(self):
        check = sh.Command("bladeRF-cli")
        blade = check("-p")
        if "bladeRF" in blade:
            return True
        else:
            return False
    
    def stopLive(self):
        
        try:
            stopit = sh.Command("killall")
            stop = stopit("grgsm_livemon_headless")
        except:
            a = 5
        try:
            stopit = sh.Command("killall")
            stop = stopit("grgsm_scanner")
        except:
            a = 5

    def find_neighbours(self):
        self.neighbours = []
        logging.info("Started neighbour search")
        cmd_main = "grgsm_livemon_headless"
        for el in self.bases:
            freq = str(el["FREQ"])
            logging.info("Starting: " + cmd_main + " -f " + freq)
            listen = sh.Command(cmd_main)

            self.data = False

            done = False
            while done == False:
                try:
                    bytes = listen("-f", freq, _out=self.process_output, _bg=True, _bg_exc=False)
                    time.sleep(10)
                    done = True
                except:
                    logging.error("livemon is up already: killing")
                    self.stopLive()
                    time.sleep(2)

            if self.data == True:
                logging.info("There is data from bts.")
                new_n = {}
                catch = sh.Command("tshark")
                logging.info("Starting tshark to capture.")
                imsis = catch("-i", "lo", "-Y", "gsmtap", "-T", "pdml",
                    "-a", "duration:10", _bg=True)
                imsis.wait()
                self.stopLive()
                for line in imsis:
                    if 'showname="List of ARFCNs =' in str(line):
                        new_n["Neighbours"] = str(line).split('showname="List of ARFCNs =')[1].split('"')[0]
                        new_n["ARFCN"] = el["ARFCN"]
                        self.neighbours.append(copy.deepcopy(new_n))
                        new_n = {}
            else:
                logging.info("There is no data from bts.")
                
            self.stopLive()
        
        return self.neighbours
        


First = Hack()
First.scanner()
if First.state:
    # First.catch_imsi(0.1)
    # print()
    # print(len(First.imsis))
    # print()
    # print(First.imsis)
    # print()
    # print()
    # print()
    # print(First.find_neighbours())
else:
    logging.error("There is no Blade connected")