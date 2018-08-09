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
import matplotlib.pyplot

# REFACTOR AND DOCUMENT


# Regex for finding the start and end times in date ranges from
# google ical format
find_time_range = re.compile(r"BEGIN:VEVENT.*?DTSTART(?:;TZID=(?P<start_tz>[^:]+))?:(?P<start>[\dT]+Z?).*?DTEND(?:;TZID=(?P<end_tz>[^:]+))?:(?P<end>[\dT]+Z?).*?END:VEVENT")

# TODO FIX timezone issues. Currently it ignores.

# This takes an ical file, finds the start and end times, then cuts
# them up into blocks of a certain minutes resolution, default 15.
def parse_ical_to_datetimes(string,minute_resolution=30,localize_to="America/New_York"):
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
def read_zipped_ical(zipped_ical, localize_to="America/New_York"):
    with zipfile.ZipFile(zipped_ical.path) as the_zip:
        if len(the_zip.namelist()) > 1:
            print("Wait a second ... "+zipped_ical.path+
                " has more than one calendar in it!")
        parsed_ical = list()
        for ical_name in the_zip.namelist():
            with the_zip.open(ical_name) as ical_file:
                parsed_ical.extend(parse_ical_to_datetimes(
                        ical_file.read(), localize_to=localize_to , 
                    )   )
    return(set(parsed_ical))

# This reads a dir of zipped files and if it's a zip then tries to
# handle it
def read_dir_of_zipped_icals(path,localize_to="America/New_York"):
    return_dict = {}
    for zipped_ical in os.scandir(path):
        if zipped_ical.name.endswith('.zip'):
            return_dict[re.sub("@.*.zip","",zipped_ical.name)
                ] = read_zipped_ical(zipped_ical,localize_to=localize_to)
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
        self.weightl = []
    def append(self,nel,ntl0,ntl1,ncl,nweightl=0):
        self.el.append(nel)   # list of tuples of edges
        self.tl0.append(ntl0) # type of source
        self.tl1.append(ntl1) # type of target
        self.cl.append(ncl)   # list of capacity of that edge
        self.weightl.append(nweightl)   # list of weights
        return(self)

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('--people',required=True,type=str)
    parser.add_argument('--meetings',required=True,type=str)
    parser.add_argument('--rooms',required=True,type=str)
    parser.add_argument('--debug',default=1,type=int)
    args = parser.parse_args()
    debug = args.debug

    people_datetimes = read_dir_of_zipped_icals(args.people,localize_to="America/New_York")
    room_datetimes   = read_dir_of_zipped_icals(args.rooms)
    meetings         = read_csv_as_meetings("meetings.csv")

    graph_lists = graph_list()
    source_vertex = "source"
    goal_vertex = "goal"
    room_vertex = "rooms"
#
    max_capacity = 1000
#
    person_capacity = float(1)
    room_capacity = float(1)
    meeting_capacity = float(1)
    a_cost = float(1)

    for each_meeting in meetings:
        this_meeting_id = each_meeting[0]
        this_meeting_possible_times = set()
        participants = each_meeting[1]
        graph_lists.append( ( this_meeting_id, goal_vertex ),
            "meeting", "goal", 
            len(participants)*person_capacity-room_capacity )
        for each_participant in participants:
            this_meeting_possible_times = \
                this_meeting_possible_times.union(\
                    people_datetimes[each_participant])
#            graph_lists.append( ( 
#                this_meeting_id+"_"+each_participant, 
#                goal_vertex ),
#                "meeting_person", "goal", 
#                (len(participants)*person_capacity-room_capacity-meeting_capacity)/len(participants), a_cost )
#### determine the blocks of time that actually work for the meeting,
#### and those are the meeting_room_time blocks, and then all the 
#### *_time nodes are piped to or from that
        for this_room in room_datetimes.keys():
            z = this_meeting_possible_times.union(\
                room_datetimes[this_room])
            for this_time in z:
                graph_lists.append( ( \
                    this_meeting_id+"_"+this_time.isoformat(),
                    this_meeting_id+"_"+this_time.isoformat()+"_"+this_room ),
                    "meeting_time", "meeting_time_room", len(participants)*person_capacity, 
                    a_cost )
                graph_lists.append( ( \
                    this_meeting_id+"_"+this_time.isoformat()+"_"+this_room,
                    this_room+"_"+this_time.isoformat() ),
                    "meeting_time_room", "room_time", room_capacity, 
                    a_cost )
                graph_lists.append( ( \
                    this_room+"_"+this_time.isoformat(), room_vertex ),
                    "room_time", "rooms", room_capacity )
                graph_lists.append( ( 
                    this_meeting_id+"_"+this_time.isoformat()+"_"+this_room, 
                    this_meeting_id ),
                    "meeting_time_room", "meeting", 
                    len(participants)*person_capacity-room_capacity, 
                    a_cost )
#meeting_capacity, a_cost )
#                for each_participant in participants:
#                    graph_lists.append( ( 
#                        this_meeting_id+"_"+this_time.isoformat()+"_"+this_room,
#                        this_meeting_id+"_"+each_participant ),
#                        "meeting_time_room", "meeting_person", 
#                        (len(participants)*person_capacity-room_capacity-meeting_capacity)/len(participants),
#                        a_cost )
            for each_participant in participants:
                for this_time in z.union( people_datetimes[each_participant]):
                    graph_lists.append( ( \
                        each_participant+"_"+this_time.isoformat() ,
                        this_meeting_id+"_"+this_time.isoformat() ) ,
                        "person_time", "meeting_time", person_capacity, 
                        a_cost )
                    graph_lists.append( ( \
                        source_vertex,
                        each_participant+"_"+this_time.isoformat() ),
                        "source", "person_time", person_capacity )
    
    graph_lists.append( ( room_vertex, goal_vertex ),
        "rooms", "goal", len(meetings)*room_capacity )

    verticies = set([ edge[0] for edge in graph_lists.el ]) \
                    .union([ edge[1] for edge in graph_lists.el ])

    name_to_id = dict(zip(verticies,list(range(0,len(verticies)))))
    id_to_name = dict(zip(list(range(0,len(verticies))),verticies))

    sanitary_edge_list = [ (name_to_id[edge[0]],name_to_id[edge[1]]) 
        for edge in graph_lists.el ]

    edge_capacity_list = graph_lists.cl

    type_map = {}
    for i, edge in enumerate(graph_lists.el):
        type_map[name_to_id[edge[0]]] = graph_lists.tl0[i]
        type_map[name_to_id[edge[1]]] = graph_lists.tl1[i]

# do graph stuff

    ebunch = []
    for i, edge in enumerate(graph_lists.el):
        ebunch.append( (edge[0],edge[1],dict([("capacity",graph_lists.cl[i]),("type0",graph_lists.tl0[i]),("type1",graph_lists.tl1[i]),("weight",graph_lists.weightl[i])])) )

    G = networkx.DiGraph()
    G.add_edges_from(ebunch)

    total_demand = sum([ len(i[1]) for i in meetings])
    G.nodes[source_vertex]['demand'] = -total_demand
    G.nodes[goal_vertex]['demand']   =  total_demand

    networkx.write_gml(G,"full.gml")

    import networksimplex
    cost, flowd = networksimplex.network_simplex(G,demand='demand',capacity='capacity',weight='weight')
    print( cost )

    new_ebunch = []
    flow_size = []
    for key in flowd:
        for target in flowd[key]:
            if flowd[key][target] > 0:
                new_ebunch.append( (key, target, flowd[key][target]))

    F = networkx.DiGraph()
    F.add_weighted_edges_from(new_ebunch,weight='flow')

    networkx.write_gml(F,"flow.gml")

    networkx.draw_spring(F,with_labels=True)
    matplotlib.pyplot.show()

#    g = igraph.Graph(sanitary_edge_list,directed=True)
#    g.es["capacity"] = edge_capacity_list
#
#    g.simplify(combine_edges=max)
#    g.vs["type"] = [     type_map[v.index] for v in list(g.vs) ]
#    g.vs["name"] = [ id_to_name[v.index] for v in list(g.vs) ]
#    g.vs["label"] = g.vs["name"]
#
#    flow = g.maxflow(name_to_id[source_vertex],name_to_id[goal_vertex],capacity="capacity")
#
#    g.es["width"] = flow.flow
#    g.es["flow"] = flow.flow
#
#    flowd = g.subgraph_edges(g.es.select(flow_gt=0))
#    flowd.write("flow.gml","gml")
#    g.write("test.gml","gml")

#    g = igraph.Graph(sanitary_edge_list,directed=True)
#    g.es["capacity"] = edge_capacity_list
#
#    g.simplify(combine_edges=max)
#    g.vs["type"] = [     type_map[v.index] for v in list(g.vs) ]
#    g.vs["name"] = [ id_to_name[v.index] for v in list(g.vs) ]
#    g.vs["label"] = g.vs["name"]
#
#    flow = g.maxflow(name_to_id[source_vertex],name_to_id[goal_vertex],capacity="capacity")
#
#    g.es["width"] = flow.flow
#    g.es["flow"] = flow.flow
#
#    flowd = g.subgraph_edges(g.es.select(flow_gt=0))
#    flowd.write("flow.gml","gml")
#    g.write("test.gml","gml")

#    if debug > 0:
#        tmp = [ ( g.vs.find(name=es.source)["type"], 
#                            id_to_name[es.source], id_to_name[es.target], 
#                            es["width"] 
#                        ) for es in g.es ]
#        tmp.sort(key=lambda x: x[1])
#        for i in tmp:
#            if i[0] == "person_time":
#                print(i)

#    layout = g.layout("kk")
#    igraph.plot(g, "tmp.png", layout = layout, 
#        edge_width=[0.0+3*width for width in g.es["width"]])

