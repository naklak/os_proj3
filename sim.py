import re
import sys

class Process:
    stats = None
    # A process is composed of an Identifier, Arrival time,
    # and a list of activites, represented by a duration
    def __init__(self,pid,arrive,activities):
        self.pid = pid
        self.arrive = arrive
        self.activities = activities
        self.current_activity = 0
        self.start_time = -1
        self.finish_time = -1
        self.service_time = 0
        self.response_times = []
    def __str__(self):
        return "Proccess " + str(self.pid) + ", Arrive " + str(self.arrive) + ": " + str(self.activities)

ARRIVAL = 0
UNBLOCK = 1

EVENT_TYPE = ["ARRIVAL", "UNBLOCK"]

class Event:
    # An event has a type, associated process, and the time it happens
    # Here I will pass a reference to an object of type Process,
    # But you could use Process ID instead if that is simpiler for you.
    def __init__(self,etype, process, time):
        self.type = etype
        self.process = process
        self.time = time
    def __lt__(self, other):
        if self.time == other.time:
            # Break Tie with event type
            if self.type == other.type:
                # Break type tie by pid
                return self.process.pid < other.process.pid
            else:
                return self.type < other.type
        else:
            return self.time < other.time
    def __str__(self):
        return "At time " + str(self.time) + ", " + EVENT_TYPE[self.type] + " Event for Process " + str(self.process.pid)

# A Priority Queue that sorts Events by '<'
class EventQueue:
    def __init__(self):
        self.queue = []
        self.dirty = False
    def push(self,item):
        if type(item) is Event:
            self.queue.append(item)
            self.dirty = True
        else:
            raise TypeError("Only Events allowed in EventQueue")
    def __prepareLookup(self, operation):
        if self.queue == []:
            raise LookupError(operation + " on empty EventQueue")
        if self.dirty:
            self.queue.sort(reverse=True)
            self.dirty = False
    def pop(self):
        self.__prepareLookup("Pop")
        return self.queue.pop()
    # Look at the next event
    def peek(self):
        self.__prepareLookup("Peek")
        return self.queue[-1]
    def empty(self):
        return len(self.queue) == 0
    def hasEvent(self):
        return len(self.queue) > 0
    def __str__(self):
        tmp = 'EventQueue('
        if len(self.queue) > 0:
            tmp = tmp + str(self.queue[0])
        for e in self.queue[1:]:
            tmp = tmp + "; " + str(e)
        tmp = tmp + ")"
        return tmp
    def __iter__(self):
        if self.dirty:
            self.queue.sort(reverse=True)
            self.dirty = False
        return iter(self.queue)

SCHED_IDS = ["FCFS", "RR", "SPN", "HRRN", "FEEDBACK"]

class Sim:  # Simulation of a scheduling algo

    def __init__(self, algo, d):
        self.debugMode = d
        self.algo = algo
        self.timer = None
        self.events = EventQueue()
        self.clock = 0
        self.runningTime = None

    def debug(self,msg,end='\n'):
        if self.debugMode:
            print("[{}] {}".format(self.clock, msg),end=end)

    def run(self):
        self.algo.initialize(self)
        move = self.getTimeForward()
        while move != None:
            if self.handleTimeDone(move):
                move = self.getTimeForward()
                while move != None and self.handleTimeDone(move):
                    move = self.getTimeForward()
            else:
                if self.timer != None:
                    self.timer -= move
                if self.runningTime != None:
                    self.runningTime -= move
                self.clock = self.events.peek().time
                self.processEvent(self.events.pop())
            while self.events.hasEvent() and self.events.peek().time == self.clock:
                self.processEvent(self.events.pop())
            if self.runningTime == None:
                self.algo.idle(self)
            move = self.getTimeForward()

    def getTimeForward(self):
        if self.events.hasEvent():
            return self.events.peek().time - self.clock
        elif self.runningTime != None:
            return self.runningTime
        else:
            return self.timer

    def handleTimeDone(self,move):
        canTimer = self.timer != None and self.timer <= move
        canStopRunning = self.runningTime != None and self.runningTime <= move
        if canTimer and (not canStopRunning or self.timer < self.runningTime):
           self.clock += self.timer
           if self.runningTime:
               self.runningTime -= self.timer
           self.timer = None
           self.algo.timeout(self)
           return True
        elif canStopRunning:
           self.clock += self.runningTime
           if self.Timer:
               self.timer -= self.runningTime
           self.runningTime = None
           self.algo.stopRunning(self)
           return True
        return False

    def processEvent(self,e):
        if e.type == ARRIVAL:
            self.algo.arrive(self,e.process)
        else: # e.type == UNBLOCK
            self.algo.unblock(self,e.process)

    def addArrival(self,p):
        self.events.push(Event(ARRIVAL, p, p.arrive))

    def addUnblockEvent(self,p,t):
        self.events.push(Event(UNBLOCK, p, self.clock+t))

    def parseProcessFile(procFile):
            procs = []
            with open(procFile) as f:
                lines = [line.rstrip() for line in f] # Read lines of the file
                lineNumber = 1
                for p in lines:
                    tmp = re.split('\s+', p)
                    # Make sure there enough values on the line
                    if len(tmp) < 2:
                        raise ValueError("Process missing activities and possible the arrival time at line " + str(lineNumber))
                    # Check to make sure there is a final CPU activity
                    # We assume the first activity is CPU, and it alternates from there.
                    # This means there must be an odd number of activities or an even number
                    # of ints on the line (the first being arrival time)
                    if len(tmp) % 2 == 1:
                        raise ValueError("Process with no final CPU activity at line " + str(lineNumber))
                    # Check to make sure each activity, represented by a duration,
                    # is an integer, and then convert it.
                    for i in range(0,len(tmp)):
                        if re.fullmatch('\d+', tmp[i]) == None:
                            raise ValueError("Invalid process on line " + str(lineNumber))
                        else:
                            tmp[i] = int(tmp[i])
                    procs.append(Process(lineNumber-1,tmp[0],tmp[1:]))
                    lineNumber = lineNumber + 1
            return procs
    
    def parseSchedulerFile(file):
        with open(file) as f:
            lines = [line.rstrip() for line in f] # Read lines of the file
            algorithm = lines[0]
            if algorithm not in SCHED_IDS:
                raise ValueError("Invalid Scheduler ID: {}".format(algorithm))
            options = {}
            lineNumber = 1
            for line in lines[1:]:
                split = re.split('\s*=\s*', line)
                if len(split) != 2:
                    raise ValueError("Invalid Scheduler option at line " + str(lineNumber))
                value = Sim.checkSchedOption(algorithm,split[0], split[1])
                if value == None:
                    raise ValueError("Invalid Scheduler option at line " + str(lineNumber))
                options[split[0]] = value
                lineNumber = lineNumber + 1
        return (algorithm,options)
    
    def checkSchedOption(algorithm, option, value):
           if algorithm == "FCFS":
               return None
           elif algorithm in ["VRR","RR"] and option == "quantum" and value.isdigit():
               return int(value)
           elif algorithm == "FEEDBACK":
               match option:
                   case "quantum":
                       if value.isdigit():
                           return int(value)
                   case "num_priorities":
                       if value.isdigit():
                           return int(value)
           elif algorithm in ["SPN","SRT","HRRN"]:
               match option:
                   case "service_given":
                       match value:
                           case "true": 
                               return True
                           case "false":
                               return False
                   case "alpha":
                       try:
                           return float(value)
                       except ValueError:
                           return None
           return None
    
