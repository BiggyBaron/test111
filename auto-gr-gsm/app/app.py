#!/usr/bin/python3
# -*- coding: UTF-8 -*-

from flask import Flask, render_template, request, Markup, send_file
import sh
import sys
import copy
import time
import logging
import datetime
import pandas as pd
import threading
import requests
import os


path = str(os.path.abspath(os.getcwd()))


app = Flask(__name__, static_url_path='/static/', 
            static_folder=path + '/templates')
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

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
        self.status = True
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
            else:
                logging.info("There is no data from bts.")
            
            self.stopLive()
        
        df = pd.DataFrame.from_dict(self.imsis)
        df.to_excel(path + '/templates/example.xlsx')
        logging.info("Saved to xlsx")
        self.status = False
    
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
        

engine = Hack()


def back(val):
    try:
        requests.get("http://127.0.0.1:7777/" + val,timeout=1)
    except requests.exceptions.ReadTimeout: #this confirms you that the request has reached server
        a = 5

@app.route("/") 
@app.route("/<way>")  # Root for login page is index "/"
def eval(way=""):

    blade_results = engine.state

    scan_results = engine.bases
    n_list = engine.neighbours

    if engine.status:
        imsi_status = "Идет работа"

    if way == "blade":
        if engine.check_blade():
            blade_results = "Is working"
        else:
            blade_results = "Not connected"

    if way == "scan":
        back("scan1")
        scan_results = "Ждите 5 минут"   

    if way == "nscan":
        back("nscan1")
        n_list = "Ждите 5 минут"   

    if way == "001":
        back("011")
        imsi_status = "Обновите через 6 минут"
    if way == "2":
        back("21")
        imsi_status = "Обновите через 2 часа"
    if way == "4":
        back("41")
        imsi_status = "Обновите через 4 часа"
    if way == "8":
        back("81")
        imsi_status = "Обновите через 8 часов"

    if way == "restart":
        reboot = sh.Command("reboot")
        reboot()

    # LONGS:
    if way == "scan1":
        engine.scanner()
        scan_results = engine.bases
    
    if way == "nscan1":
        n_list = engine.find_neighbours()

    if way == "011":
        time = 0.02
        engine.catch_imsi(time)
        imsi_status = "Скачивай"

    if way == "11":
        time = 1
        engine.catch_imsi(time)
        imsi_status = "Скачивай"
    
    if way == "21":
        time = 2
        engine.catch_imsi(time)
        imsi_status = "Скачивай"


    if way == "41":
        time = 4
        engine.catch_imsi(time)
        imsi_status = "Скачивай"

    if way == "81":
        time = 8
        engine.catch_imsi(time)
        imsi_status = "Скачивай"
    
    return render_template(
        "index.html", **locals())


if __name__ == "__main__":
    
    df = pd.DataFrame.from_dict([{"Тут":"Ничего нет"}])
    df.to_excel(path + '/templates/example.xlsx')
    
    app.run(host='0.0.0.0', port=7777) 