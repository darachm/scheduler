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

# REFACTOR AND DOCUMENT

class graph_list():
    def __init__(self):
        self.el = []
        self.tl0 = []
        self.tl1 = []
        self.cl = []

def append_graph_list(gl,nel,ntl0,ntl1,ncl):
    gl.el.append(nel)
    gl.tl0.append(ntl0)
    gl.tl1.append(ntl1)
    gl.cl.append(ncl)
    return(gl)

# Regex for finding the start and end times in date ranges from
# google ical format
find_time_range = re.compile(r"BEGIN:VEVENT.*?DTSTART:([\dT]+Z).*?DTEND:([\dT]+Z).*?END:VEVENT")

# This takes an ical file, finds the start and end times, then cuts
# them up into blocks of a certain minutes resolution, default 15.
def parse_ical_to_datetimes(string,minute_resolution=15):
    possible_datetimes = list()
    # We decode as utf8 and replace all line endings to slurp a 
    # string in for each ical
    for i in find_time_range.finditer(string.decode("utf-8").replace("\r\n","")):
        # The two groups should match
        (start, end) = i.groups()
        # They each get parsed... is there a way to `map` this?
        (start, end) = (iso8601.parse_date(start), 
            iso8601.parse_date(end)) 
        # Then we round the minutes of the start date to the next
        # certain minutes window
        this_datetime = start.replace(
            minute=math.ceil(start.minute/minute_resolution)*
                minute_resolution
            )
        # While it ain't over, 
        while this_datetime < end:
            # we append this block of time
            possible_datetimes.append(this_datetime)
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
    return(parsed_ical)

# This reads a dir of zipped files and if it's a zip then tries to
# handle it
def read_dir_of_zipped_icals(path):
    return_dict = {}
    for zipped_ical in os.scandir(path):
        if zipped_ical.name.endswith('.zip'):
            return_dict[zipped_ical.name.replace(".zip","")] = \
                read_zipped_ical(zipped_ical)
    return(return_dict)

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('--people',required=True,type=str)
    parser.add_argument('--meetings',required=True,type=str)
    parser.add_argument('--rooms',required=True,type=str)
    parser.add_argument('--debug',default=1,type=int)
    args = parser.parse_args()
    debug = args.debug

    people_datetimes = read_dir_of_zipped_icals(args.people)
    print(people_datetimes)


    exit();

    meetings = read_csv_to_list(args.meetings)
    schedules = read_csv_to_list(args.schedules)
    rooms = read_csv_to_list(args.rooms)

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

    graph_lists = graph_list()
    source_vertex = "source"
    goal_vertex = "goal"
    max_capacity = 1000

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
