#!/usr/bin/python3

#import igraph
import networkx
import argparse
import csv
import os
import zipfile
import re
import iso8601
import math
import datetime
from dateutil.tz import gettz

# REFACTOR AND DOCUMENT


# Regex for finding the start and end times in date ranges from
# google ical format
find_time_range = re.compile(r"BEGIN:VEVENT.*?DTSTART(?:;TZID=(?P<start_tz>[^:]+))?:(?P<start>[\dT]+Z?).*?DTEND(?:;TZID=(?P<end_tz>[^:]+))?:(?P<end>[\dT]+Z?).*?END:VEVENT")

# TODO FIX timezone issues. Currently it ignores.

# This takes an ical file, finds the start and end times, then cuts
# them up into blocks of a certain minutes resolution, default 15.
def parse_ical_to_datetimes(string,minute_resolution,localize_to="America/New_York"):
    possible_datetimes = list()
    # We decode as utf8 and replace all line endings to slurp a 
    # string in for each ical
    for i in find_time_range.finditer(string.decode("utf-8").replace("\r\n","")):
        # The two groups should match
        (start, end) = (i.group("start"), i.group("end"))
        # They each get parsed... is there a way to `map` this?
        (start, end) = (iso8601.parse_date(start), 
            iso8601.parse_date(end)) 
        # Set timezones
        if i.group("start_tz") == None:
            start = start.replace(tzinfo=datetime.timezone.utc)
        else:
            start = start.replace(tzinfo=gettz(name=i.group("start_tz")))
        if i.group("end_tz") == None:
            end = end.replace(tzinfo=datetime.timezone.utc)
        else:
            end = end.replace(tzinfo=gettz(name=i.group("end_tz")))
        # Then we round the minutes of the start date to the next
        # certain minutes window, and set the timezone if needed
        this_datetime = start.replace(
            minute=math.ceil(start.minute/minute_resolution)*
                minute_resolution
            )
        # While it ain't over, 
        while this_datetime < end:
            # we append this block of time
            possible_datetimes.append(\
                this_datetime.astimezone(tz=gettz(name=localize_to))
                )
            # and increment to the next block of time
            this_datetime += datetime.timedelta(minutes=minute_resolution)
    # So then we return the list of blocks of time this person should
    # be free, discretized according to the setting
    return(possible_datetimes)

# This takes a zipped ical and tries to open all the calendars inside
# (should be one) and then parse and extend each one
def read_zipped_ical(zipped_ical, minute_resolution, 
        localize_to="America/New_York"):
    with zipfile.ZipFile(zipped_ical.path) as the_zip:
        if len(the_zip.namelist()) > 1:
            print("Wait a second ... "+zipped_ical.path+
                " has more than one calendar in it!")
        parsed_ical = list()
        for ical_name in the_zip.namelist():
            with the_zip.open(ical_name) as ical_file:
                parsed_ical.extend(parse_ical_to_datetimes(
                        ical_file.read(), 
                        minute_resolution=minute_resolution,
                        localize_to=localize_to , 
                    )   )
    return(set(parsed_ical))

# This reads a dir of zipped files and if it's a zip then tries to
# handle it
def read_dir_of_zipped_icals(path,minute_resolution,
        localize_to="America/New_York"):
    return_dict = {}
    for zipped_ical in os.scandir(path):
        if zipped_ical.name.endswith('.zip'):
            return_dict[re.sub("@.*.zip","",zipped_ical.name)
                ] = read_zipped_ical(zipped_ical,
                    minute_resolution=minute_resolution,
                    localize_to=localize_to)
    return(return_dict)

def read_csv_as_meetings(path):
    with open(path,"r") as f:
        meetings = list(csv.reader(f))[1:]
    return( list( map( 
        lambda x: [x[0].strip(), x[1].strip(), set(re.split(r"\s", x[2].strip()))] , 
        meetings
        ) ) )

#class graph_list():
#    def __init__(self):
#        self.el = []
#        self.tl0 = []
#        self.tl1 = []
#        self.cl = []
#        self.weightl = []
#    def append(self,nel,ntl0,ntl1,ncl,nweightl=0):
#        self.el.append(nel)   # list of tuples of edges
#        self.tl0.append(ntl0) # type of source
#        self.tl1.append(ntl1) # type of target
#        self.cl.append(ncl)   # list of capacity of that edge
#        self.weightl.append(nweightl)   # list of weights
#        return(self)

class hairball():
    def __init__(self):
        self.meetings = {}
        self.persons_by_time = {}
    def append_meeting(self,meeting_id,meeting_persons,meeting_times):
        self.meetings[meeting_id] = { 'persons': meeting_persons, 'plausible_times': meeting_times }
        return(self)
    def set_up_people(self,some_start_time,persons):
        try:
            self.persons_by_time[some_start_time] = self.persons_by_time[some_start_time].union(set(persons))
        except:
            self.persons_by_time[some_start_time] = set(persons)

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('--people',required=True,type=str)
    parser.add_argument('--meetings',required=True,type=str)
    parser.add_argument('--rooms',required=True,type=str)
    parser.add_argument('--debug',default=1,type=int)
    parser.add_argument('--resolution',default=30,type=int)
    args = parser.parse_args()
    debug = args.debug

    people_datetimes = read_dir_of_zipped_icals(args.people,
        minute_resolution=args.resolution,
        localize_to="America/New_York")
    room_datetimes   = read_dir_of_zipped_icals(args.rooms,
        minute_resolution=args.resolution,
        localize_to="America/New_York")
    meetings         = read_csv_as_meetings("meetings.csv")

    hairball = hairball()

    for each_meeting in meetings:

        this_meeting_id = each_meeting[0]
        duration = each_meeting[1]
        participants = each_meeting[2]

        this_meeting_possible_times = set()

        for each_participant in participants:
            this_meeting_possible_times = \
                this_meeting_possible_times.union(\
                    people_datetimes[each_participant])

        for this_room in room_datetimes.keys():
            this_meeting_room_possibile_times = \
                this_meeting_possible_times.union(\
                room_datetimes[this_room])

        this_meeting_possible_starts = sorted(list(this_meeting_possible_times))
        starts = list()

        for i in range(len(this_meeting_possible_starts)):
            use_it = 1
            for j in range(1,-(-int(duration)//int(args.resolution))):
                if  (this_meeting_possible_starts[i]+datetime.timedelta(minutes=args.resolution)*j) not in this_meeting_possible_times:
                    use_it = 0
                    break
            if use_it == 1:
                starts.append(this_meeting_possible_starts[i])


        hairball.append_meeting(this_meeting_id, participants, starts)


    for each_meeting_id in hairball.meetings.keys():
        for each_time in hairball.meetings[each_meeting_id]['plausible_times']:
            hairball.set_up_people(each_time,hairball.meetings[each_meeting_id]['persons'])


    print(hairball.persons_by_time)
        

# next, create some sort of iterator thing that will try every combination of
#   meeting start times

# it should make a copy of the hairball persons by time before starting, and
#   delete people out of timeslots as it goes, if it can't delete then fail

# also implement rooms like the people, and do the same before persons


