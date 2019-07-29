#!/usr/bin/env python3
import asyncio

import aiofiles
import aiohttp
from aiohttp import ClientSession

import base64

import timeit

import argparse

import re

import atexit


class StoreDictKeyPair(argparse.Action):
    def __init__(self, option_strings, dest, nargs=None, **kwargs):
         self.myDict = {}
         super(StoreDictKeyPair, self).__init__(option_strings, dest, nargs=nargs, **kwargs)
    def __call__(self, parser, namespace, values, option_string=None):
        k,v = values.split(":")
        self.myDict.update({k:v})
        setattr(namespace, self.dest, self.myDict)

class ArgManager:
    def __init__(self):
        self.parser = argparse.ArgumentParser(description=" [state intent]")
        self.parser = argparse.ArgumentParser(description="[state intent]\nExample command: %(prog)s https://url.here/endpoint",
            usage='use "%(prog)s --help" for more information',
            formatter_class=argparse.RawTextHelpFormatter)
        self.parser.add_argument("-u", "--user", help= "credentials in the form user:password",type=str,metavar= "")
        self.parser.add_argument("-H", "--header",help= "additional header for request", action=StoreDictKeyPair ,default = {},metavar= "",dest='header')
        self.parser.add_argument("-d", "--data", help="data to send with request",type=str,metavar= '')
        self.parser.add_argument("-X","--call-type",help="request type to use", type=str,default="GET",metavar= '',choices=["GET","POST","PUT","DELETE"])
        self.parser.add_argument("url",help="url to use",type=str)
        self.args = self.parser.parse_args()

    def parseURLList(self,url):
        urlList = []
        subString = re.search(r"\[(.*?)\]|\{(.*?)\}", url)
        if subString == None:
            urlList.append(url)
            return urlList
        elif subString.group(0).startswith('['):
            parseStep = re.split(":",subString.group(0).strip('[]'))   
            nth = 1
            if len(parseStep) > 1:
                nth = int(parseStep[1])
            parseRange = re.split("-",parseStep[0])   
            start = int(parseRange[0])
            end = int(parseRange[1])
            for x in range(start,end,nth):
                modifiedUrl = re.sub(r"\[(.*?)\]",str(x),url,1)
                urlList += self.parseURLList(modifiedUrl) or []
        elif subString.group(0).startswith('{'):
            parseElems = re.split(",",subString.group(0).strip('{}'))   
            for x in parseElems:
                modifiedUrl = re.sub(r"\{(.*?)\}",x,url,1)
                urlList += self.parseURLList(modifiedUrl) or []
        return urlList

    def EncodedAuthHeader(self, userPass):
        if userPass != None:
            creds = base64.b64encode(bytes(userPass,'utf-8'))
            return {"Authorization" : "Basic " + creds.decode("utf-8")}
        return {}

class SessionController:
    def __init__(self):
        self.loop = asyncio.get_event_loop()
        self.mySession = ClientSession(connector=aiohttp.TCPConnector(ssl=False),loop=self.loop)
        atexit.register(lambda: asyncio.get_event_loop().run_until_complete(self.endSession()))
    def __enter__(self):
        return self
    async def __exit__(self, exc_type, exc_value, traceback):
        await self.endSession()
    async def endSession(self):
        await self.mySession.close()

    def batch(self,iterable, n=1):
        l = len(iterable)
        for ndx in range(0, l, n):
            yield iterable[ndx:min(ndx + n, l)]

    # this could be coded better. It doesn't make sense at a glance
    # some checking and reporting for pending tasks that time out should be built in
    async def runMethodBatch(self,maxBatch,asyncMethodList):
        # there's to be a prettier way to do this. I'll come back to it
        done = []
        pending = []
        index = 0
        for elem in self.batch(asyncMethodList,maxBatch):
            print("batch ", index, "started")
            print(timeit.default_timer())
            index += 1
            tasks = []
            for method in elem:
                task = asyncio.create_task(method())
                tasks.append(task)
            myDone,myPending = await asyncio.wait(tasks)
            done.append(myDone)
            pending.append(myPending)
        return done,pending
    def buildCallTaskList(self,session,urlList,callType,headers,data):
        tasksList = []
        for url in urlList:
            t = lambda x=callType,y=url,z=headers,d=data: session.request(x,y,headers=z,data=d)
            tasksList.append(t)
        return tasksList
    
async def main():
    sessionController = SessionController()
    session = sessionController.mySession
    myArgManager = ArgManager()

    headers = myArgManager.args.header
    headers.update(myArgManager.EncodedAuthHeader(myArgManager.args.user))

    urlList = myArgManager.parseURLList(myArgManager.args.url)
    myData = myArgManager.args.data
    callList = sessionController.buildCallTaskList(session, urlList,myArgManager.args.call_type,headers,myData)

    done,pending = await sessionController.runMethodBatch(500,callList)
    for elem in done:
        print("\n************\n")
        for x in elem:
            print(str(x.result()))
            text = await x.result().text()
            print(text)


if __name__ == '__main__':
    start = timeit.default_timer()
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
    stop = timeit.default_timer()
    timeTotal = stop-start
    print('Time: ', timeTotal)  


