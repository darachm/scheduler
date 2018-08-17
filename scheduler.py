#!/usr/bin/python3

#import igraph
import argparse
import csv
import os
import zipfile
import re
import itertools
import copy
import iso8601
import math
import datetime
import dateutil.tz
import icalendar

# REFACTOR AND DOCUMENT

# Regex for finding the start and end times in date ranges from
# google ical format
find_time_range = re.compile(r"BEGIN:VEVENT.*?DTSTART(?:;TZID=(?P<start_tz>[^:]+))?:(?P<start>[\dT]+Z?).*?DTEND(?:;TZID=(?P<end_tz>[^:]+))?:(?P<end>[\dT]+Z?).*?END:VEVENT")

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
            start = start.replace(tzinfo=dateutil.tz.gettz(name=i.group("start_tz")))
        if i.group("end_tz") == None:
            end = end.replace(tzinfo=datetime.timezone.utc)
        else:
            end = end.replace(tzinfo=dateutil.tz.gettz(name=i.group("end_tz")))
        # Then we round the minutes of the start date to the next
        # certain minutes window, and set the timezone if needed
        this_datetime = start.replace(minute=(math.ceil(start.minute/minute_resolution)*minute_resolution)%60)
        # While it ain't over, 
        while this_datetime < end:
            # we append this block of time
            possible_datetimes.append(\
                this_datetime.astimezone(tz=dateutil.tz.gettz(name=localize_to))
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



def format_meeting_as_ical_event(some_meeting):
    event = icalendar.Event()
    event['meeting_id'] = str(some_meeting['meeting_id'])
    event['room'] = str(some_meeting['room'])
    event['participants'] = str(some_meeting['participants'])
    event['summary'] = event['meeting_id'] + " happening in " +\
        event['room'] + ", with the following participants: " + \
        event['participants']
    event['dtstart'] = some_meeting['start_time']
    event['dtend'] = some_meeting['end_time']
    return(event)
    

def write_out_a_schedule(a_schedule,an_output_dir):
    an_id = ""
    for i in a_schedule:
        an_id += i['start_time']
    with open(an_output_dir+"/"+an_id+".ical","wb") as f:
        cal = icalendar.Calendar()
        for each_meeting in a_schedule:
            cal.add_component(format_meeting_as_ical_event(each_meeting))
        f.write(cal.to_ical())


def schedule_report(a_schedule):
    return_string = "I found a schedule that should work:\n"
    for meeting in a_schedule:
        return_string += "\t"
        return_string += meeting['meeting_id'] 
        return_string += " : "
        return_string += str(meeting['participants'])
        return_string += "\n"
        return_string += "\t\t"
        return_string += meeting['start_time'] 
        return_string += " - "
        return_string += meeting['start_time']
        return_string += "\n"
    return(return_string)


class hairball():
    def __init__(self):
        self.meetings = {}
        self.persons_by_time = {}
        self.rooms_by_time = {}
    def new_meeting(self,meeting_id,duration,meeting_persons,meeting_times):
        self.meetings[meeting_id] = { 'persons': meeting_persons, 
            'duration': duration, 'plausible_times': meeting_times }
        return(self)
    def set_up_people(self,some_start_time,persons):
        try:
            self.persons_by_time[some_start_time] = self.persons_by_time[some_start_time].union(set(persons))
        except:
            self.persons_by_time[some_start_time] = set(persons)
    def set_up_room(self,some_start_time,a_room):
        try:
            self.rooms_by_time[some_start_time] = self.rooms_by_time[some_start_time].union(set([a_room]))
        except:
            self.rooms_by_time[some_start_time] = set([a_room])


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('--people',required=True,type=str)
    parser.add_argument('--meetings',required=True,type=str)
    parser.add_argument('--rooms',required=True,type=str)
    parser.add_argument('--output-dir',required=True,type=str)
    parser.add_argument('--debug', action='store_true')
    parser.add_argument('--resolution',default=30,type=int)
    args = parser.parse_args()

    people_datetimes = read_dir_of_zipped_icals(args.people,
        minute_resolution=args.resolution,
        localize_to="America/New_York")
    room_datetimes   = read_dir_of_zipped_icals(args.rooms,
        minute_resolution=args.resolution,
        localize_to="America/New_York")
    meetings         = read_csv_as_meetings(args.meetings)

    if args.debug:
        print()
        for i in people_datetimes:
            print(i)
            print(sorted(people_datetimes[i]))
        print()
        for i in room_datetimes:
            print(i)
            print(sorted(room_datetimes[i]))
        print()
        print(meetings)
        print()

    hairball = hairball()

    all_possible_roomtimes = set()
    for each_room in room_datetimes:
        all_possible_roomtimes = \
            all_possible_roomtimes.union(room_datetimes[each_room])

    for each_meeting in meetings:

        this_meeting_id = each_meeting[0]
        duration = each_meeting[1]
        participants = list(each_meeting[2])

        this_meeting_possible_times = set(people_datetimes[participants[0]])
        for each_participant in participants[1:]:
            this_meeting_possible_times = \
                this_meeting_possible_times.intersection(\
                    set(people_datetimes[each_participant]))

        this_meeting_possible_times = \
            this_meeting_possible_times.intersection(set(all_possible_roomtimes))

        this_meeting_possible_starts = sorted(list(this_meeting_possible_times))

        starts = list()

        for i in range(len(this_meeting_possible_starts)):

            use_it = 1

            for j in range(1,-(-int(duration)//int(args.resolution))):

                if  (this_meeting_possible_starts[i]+\
                        datetime.timedelta(minutes=args.resolution)*j) \
                        not in this_meeting_possible_times:

                    use_it = 0
                    break

            if use_it == 1:
                starts.append(this_meeting_possible_starts[i])

        hairball.new_meeting(this_meeting_id, duration, participants, starts)


    for each_meeting_id in hairball.meetings.keys():
        for each_time in hairball.meetings[each_meeting_id]['plausible_times']:
            hairball.set_up_people(each_time,hairball.meetings[each_meeting_id]['persons'])

            for this_room in room_datetimes.keys():
                if each_time in room_datetimes[this_room]:
                    hairball.set_up_room(each_time,this_room)

    if args.debug:
        for i in hairball.meetings:
            print(i)
            print(sorted(hairball.meetings[i]['plausible_times']))
            print()
        for i in hairball.persons_by_time:
            print(i)
            print(sorted(hairball.persons_by_time[i]))
            print()

    schedules = list()
    tmp_schedules = dict()
    meeting_ids = list(hairball.meetings.keys())

    for tuple_times in list(itertools.product(*[hairball.meetings[i]['plausible_times'] for i in meeting_ids])):

        if args.debug:
            print("a tuple tested")

        local_hairball = copy.deepcopy(hairball)

        keep_it = 1

        for j in range(0,len(meeting_ids)):

            if args.debug:
                print("\t"+meeting_ids[j]+" at "+str(tuple_times[j]))

            time_block_list = [ tuple_times[j] + \
                    k*datetime.timedelta(minutes=args.resolution) \
                    for k in range(0,-(-int(local_hairball\
                    .meetings[meeting_ids[j]]['duration'])// \
                    int(args.resolution))) ]

            try:
                for held_room in list(local_hairball.rooms_by_time[tuple_times[j]]):
    
                    try:
                        if any( [ held_room not in local_hairball.rooms_by_time[k] for k in time_block_list ] ):
                            if args.debug:
                                print("\t\tthat one's booked")
                            continue
                    except:
                        if args.debug:
                            print("\t\terror in finding room times")
                        continue
    
                    for time_block in time_block_list:
    
                        local_hairball.rooms_by_time[time_block] = \
                            local_hairball.rooms_by_time[time_block] - \
                            set([held_room])
    
                    local_hairball.meetings[meeting_ids[j]]['room'] =  \
                        held_room
                    if args.debug:
                        print("\t\tbooked "+held_room)
    
                    break
            except:
                raise("howd that get through")

            try:
                if local_hairball.meetings[meeting_ids[j]]['room'] == "":
                    pass
            except:
                if args.debug:
                    print("\t\tno room found")
                keep_it = 0
                break

            for time_block in time_block_list:

                try:
                    if set(local_hairball.meetings[meeting_ids[j]]['persons'])\
                            <= local_hairball.persons_by_time[time_block] :
    
                        local_hairball.persons_by_time[time_block] = \
                            local_hairball.persons_by_time[time_block] - \
                            set(local_hairball.meetings[meeting_ids[j]]['persons'])
    
                    else:
                        if args.debug:
                            print("\t\tperson conflict")
                        keep_it = 0
                        break

                except:
                    if args.debug:
                        print("\t\tsomething broke in the person reserving")
                    keep_it = 0
                    break

            if keep_it == 0:
                break 

        if keep_it == 0:
            continue 

        if keep_it == 1:
            if args.debug:
                print("a tuple kept")
            scheduled_meetings = [ { 'meeting_id': meeting_ids[j], 
                        'start_time': tuple_times[j].astimezone(dateutil.tz.tzutc()).strftime("%Y%m%dT%H%M%SZ"),
                        'end_time': (tuple_times[j]+datetime.timedelta(minutes=int(local_hairball.meetings[meeting_ids[j]]['duration']))).astimezone(dateutil.tz.tzutc()).strftime("%Y%m%dT%H%M%SZ"),
                        'participants': local_hairball.meetings[meeting_ids[j]]['persons'],
                        'room': local_hairball.meetings[meeting_ids[j]]['room'] } \
                        for j in range(0,len(meeting_ids)) ]
            schedules.append(scheduled_meetings)
            write_out_a_schedule(scheduled_meetings,args.output_dir)
            print(schedule_report(scheduled_meetings))

    for each_schedule in range(len(schedules)):

        if args.debug:
            print(each_schedule)






