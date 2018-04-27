#!/usr/bin/python3

import igraph
import argparse
import csv

# Read in 

#main
#  take cli arguments
#  read a folder of gcal zips, unzip and read and parse
#  build bipartite graph of people and times
#  build as flow problem
#  see if flow problem can eliminate two people times things

def read_csv_to_list(path):
  with open(path,"r") as f:
    return list(csv.reader(f))[1:]

def append_graph_list(gl,nel,ntl0,ntl1,ncl):
  gl.el.append(nel)
  gl.tl0.append(ntl0)
  gl.tl1.append(ntl1)
  gl.cl.append(ncl)
  return(gl)

class graph_list():
  def __init__(self):
    self.el = []
    self.tl0 = []
    self.tl1 = []
    self.cl = []

if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  parser.add_argument('--meetings',required=True,type=str)
  parser.add_argument('--schedules',required=True,type=str)
  parser.add_argument('--rooms',required=True,type=str)
  parser.add_argument('--debug',default=1,type=int)
  args = parser.parse_args()

  debug = args.debug

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
    try:
      times_per_person[schedule[0]].add(schedule[1])
    except:
      times_per_person[schedule[0]] = set([schedule[1]])

  times_per_room = {}
  for room in rooms:
    try:
      times_per_room[room[0]].add(room[1])
    except:
      times_per_room[room[0]] = set(room[1])

  graph_lists = graph_list()
#  graph_lists.el = [] #{ "el":[], "tl0":[], "tl1":[], "cl":[] }
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
              "meet_time_room", "room_time", 1 )
            graph_lists = append_graph_list(graph_lists,
              ( room+"_"+possible_time , 
                goal_vertex ), 
              "room_time", "goal", 1 )
            graph_lists = append_graph_list(graph_lists,
              ( meet+"_"+possible_time+"_"+room ,
                meet ), 
              "meet_time_room", "meet", len(meet_persons)-1 )
            graph_lists = append_graph_list(graph_lists,
              ( meet ,
                goal_vertex ), 
              "meet", "goal", len(meet_persons)-1 )

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
  g.vs["type"] = [   type_map[v.index] for v in list(g.vs) ]
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
    edge_width=[0.1+2*width for width in g.es["width"]])


  tmp = [ ( g.vs.find(name=es.source)["type"], 
            id_to_name[es.source], id_to_name[es.target], 
            es["width"] 
          ) for es in g.es ]
  tmp.sort(key=lambda x: x[1])
  for i in tmp:
    if i[0] == "meet_time_room" and ( i[3] > 0 ): 
      print(i)
