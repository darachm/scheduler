#!/usr/bin/python3

import igraph
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
def parse_ical_to_datetimes(string,minute_resolution=30):
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
                this_datetime.astimezone(datetime.timezone.utc)
                )
            # and increment to the next block of time
            this_datetime += datetime.timedelta(minutes=minute_resolution)
    # So then we return the list of blocks of time this person should
    # be free, discretized according to the setting
    return(possible_datetimes)

# This takes a zipped ical and tries to open all the calendars inside
# (should be one) and then parse and extend each one
def read_zipped_ical(zipped_ical):
    with zipfile.ZipFile(zipped_ical.path) as the_zip:
        if len(the_zip.namelist()) > 1:
            print("Wait a second ... "+zipped_ical.path+
                " has more than one calendar in it!")
        parsed_ical = list()
        for ical_name in the_zip.namelist():
            with the_zip.open(ical_name) as ical_file:
                parsed_ical.extend(parse_ical_to_datetimes(
                        ical_file.read()
                    )   )
    return(set(parsed_ical))

# This reads a dir of zipped files and if it's a zip then tries to
# handle it
def read_dir_of_zipped_icals(path):
    return_dict = {}
    for zipped_ical in os.scandir(path):
        if zipped_ical.name.endswith('.zip'):
            return_dict[zipped_ical.name
                    .replace(".zip","")
                    .replace("@nyu.edu.ical","")
                ] = read_zipped_ical(zipped_ical)
    return(return_dict)

def read_csv_as_meetings(path):
    with open(path,"r") as f:
        meetings = list(csv.reader(f))[1:]
    return( list( map( 
        lambda x: [x[0].strip(), set(re.split(r"\s", x[1].strip()))] , 
        meetings
        ) ) )

class graph_list():
    def __init__(self):
        self.el = []
        self.tl0 = []
        self.tl1 = []
        self.cl = []
    def append(self,nel,ntl0,ntl1,ncl):
        self.el.append(nel)   # list of tuples of edges
        self.tl0.append(ntl0) # type of source
        self.tl1.append(ntl1) # type of target
        self.cl.append(ncl)   # list of capacity of that edge
        return(self)

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('--people',required=True,type=str)
    parser.add_argument('--meetings',required=True,type=str)
    parser.add_argument('--rooms',required=True,type=str)
    parser.add_argument('--debug',default=1,type=int)
    args = parser.parse_args()
    debug = args.debug

    people_datetimes = read_dir_of_zipped_icals(args.people)
    room_datetimes   = read_dir_of_zipped_icals(args.rooms)
    meetings         = read_csv_as_meetings("meetings.csv")

    graph_lists = graph_list()
    source_vertex = "source"
    goal_vertex = "goal"
    max_capacity = 1000

    for each_meeting in meetings:
        this_meeting_id = each_meeting[0]
        this_meeting_possible_times = set()
        graph_lists.append( ( this_meeting_id, goal_vertex ),
            "meeting", "goal", len(each_meeting[1])-1 )
        for each_participant in each_meeting[1]:
            this_meeting_possible_times = \
                this_meeting_possible_times.union(\
                    people_datetimes[each_participant])
        for this_room in room_datetimes.keys():
            for each_meeting_time in this_meeting_possible_times:
                graph_lists.append( ( \
                    this_meeting_id+"_"+each_meeting_time.isoformat()+"_"+this_room,
                    this_meeting_id ),
                    "meeting_time_room", "meeting", len(each_meeting[1])-1 )
            z = this_meeting_possible_times.union(\
                room_datetimes[this_room])
            for this_time in z:
                graph_lists.append( ( \
                    this_room+"_"+this_time.isoformat(), goal_vertex ),
                    "room_time", "goal", 1 )
            for each_participant in each_meeting[1]:
                for this_time in z.union( people_datetimes[each_participant]):
                    graph_lists.append( ( \
                        each_participant+"_"+this_time.isoformat() ,
                        this_meeting_id+"_"+this_time.isoformat()+"_"+this_room ) ,
                        "person_time", "meeting_time_room", 1 )
                    graph_lists.append( ( \
                        source_vertex,
                        each_participant+"_"+this_time.isoformat() ),
                        "source", "person_time", 1 )


    for i in graph_lists.el:
        print(i)

#                graph_lists.append( ( this_meeting_id+"_"+i.isoformat()+"_"))

#    graph_lists = append_graph_list(graph_lists,
#        ( meet+"_"+possible_time+"_"+room, meet ), 
#        "meet_time_room", "meet", len(meet_persons)-0.1 )

    exit();

    persons_per_meeting = {}
    for meet in meetings:
        persons_at_meeting = meet[1].split()
        for person in persons_at_meeting:
            try:
                persons_per_meeting[meet[0]].add(person)
            except:
                persons_per_meeting[meet[0]] = set([person])

    times_per_person = {}
    for schedule in schedules:
        person_times = schedule[1].split()
        for this_person_time in person_times:
            try:
                times_per_person[schedule[0]].add(this_person_time)
            except:
                times_per_person[schedule[0]] = set([this_person_time])

    times_per_room = {}
    for room in rooms:
        room_times = room[1].split()
        for this_room_time in room_times:
            try:
                times_per_room[room[0]].add(this_room_time)
            except:
                times_per_room[room[0]] = set([this_room_time])


    for person, times in times_per_person.items():
        graph_lists = append_graph_list(graph_lists,
            (source_vertex, person), "source", "person", max_capacity)
        for t in times:
            graph_lists = append_graph_list(graph_lists,
                (person, person+"_"+t), "person", "person_time", 1)

    for meet, meet_persons in persons_per_meeting.items():
        these_persons = list(meet_persons)
        possible_times = times_per_person[these_persons[0]]
        for each_person in these_persons[1:]:
            possible_times = possible_times & times_per_person[each_person]
        for possible_time in list(possible_times):
            for room, room_times in times_per_room.items():
                if possible_time in room_times:
                    for meet_person in meet_persons:
                        graph_lists = append_graph_list(graph_lists,
                            ( meet_person+"_"+possible_time ,
                                meet+"_"+possible_time+"_"+room ), 
                            "person_time", "meet_time_room", 1 )
                        graph_lists = append_graph_list(graph_lists,
                            ( meet+"_"+possible_time+"_"+room ,
                                room+"_"+possible_time ), 
                            "meet_time_room", "room_time", 0.1 )
                        graph_lists = append_graph_list(graph_lists,
                            ( room+"_"+possible_time , 
                                goal_vertex ), 
                            "room_time", "goal", 0.1 )
                        graph_lists = append_graph_list(graph_lists,
                            ( meet+"_"+possible_time+"_"+room ,
                                meet ), 
                            "meet_time_room", "meet", len(meet_persons)-0.1 )
                        graph_lists = append_graph_list(graph_lists,
                            ( meet ,
                                goal_vertex ), 
                            "meet", "goal", len(meet_persons)-0.1 )

# Build index
    verticies = set()
    for edge in graph_lists.el:
        verticies.add(edge[0])
        verticies.add(edge[1])
    name_to_id = {}
    id_to_name = {}
    id_counter = 0
    for vertex in verticies:
        id_to_name[id_counter] = vertex
        name_to_id[vertex] = id_counter
        id_counter += 1
    
    sanitary_edge_list = []
    edge_capacity_list = []
    type_map = {}
    for i, edge in enumerate(graph_lists.el):
        sanitary_edge_list.append(( name_to_id[edge[0]], name_to_id[edge[1]] ))
        edge_capacity_list.append(graph_lists.cl[i])
        type_map[name_to_id[edge[0]]] = graph_lists.tl0[i]
        type_map[name_to_id[edge[1]]] = graph_lists.tl1[i]

    g = igraph.Graph(sanitary_edge_list,directed=True)
    g.es["capacity"] = edge_capacity_list

    g.simplify(combine_edges=max)
    g.vs["type"] = [     type_map[v.index] for v in list(g.vs) ]
    g.vs["name"] = [ id_to_name[v.index] for v in list(g.vs) ]
    g.vs["label"] = g.vs["name"]

    flow = g.maxflow(name_to_id[source_vertex],name_to_id[goal_vertex],capacity="capacity")


    g.es["width"] = flow.flow

    if debug > 0:
        tmp = [ ( g.vs.find(name=es.source)["type"], 
                            id_to_name[es.source], id_to_name[es.target], 
                            es["width"] 
                        ) for es in g.es ]
        tmp.sort(key=lambda x: x[1])
        for i in tmp:
            if i[0] == "person_time":
                print(i)

    layout = g.layout("kk")
    igraph.plot(g, "tmp.png", layout = layout, 
        edge_width=[0.0+3*width for width in g.es["width"]])

    tmp = [ ( g.vs.find(name=es.source)["type"], 
                        id_to_name[es.source], id_to_name[es.target], 
                        es["width"] 
                    ) for es in g.es ]
    tmp.sort(key=lambda x: x[1])
    for i in tmp:
        if i[0] == "meet_time_room" and ( i[3] > 0 ): 
            print(i)
