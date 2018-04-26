#!/usr/bin/python3

import igraph
import argparse
import csv

# 

# Read in 

#main
#  take cli arguments
#  read a folder of gcal zips, unzip and read and parse
#  build bipartite graph of people and times
#  build as flow problem
#  see if flow problem can eliminate two people times things

if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  parser.add_argument('--meetings',type=str)
  parser.add_argument('--schedules',type=str)
  args = parser.parse_args()

  with open(args.meetings,"r") as f:
    meetings = list(csv.reader(f))[1:]
  with open(args.schedules,"r") as f:
    schedules = list(csv.reader(f))[1:]

  persons_per_meeting = {}
  times_per_person = {}

  for meet in meetings:
    persons_at_meeting = meet[1].split()
    for person in persons_at_meeting:
      try:
        persons_per_meeting[meet[0]].append(person)
      except:
        persons_per_meeting[meet[0]] = [person]

  for schedule in schedules:
    try:
      times_per_person[schedule[0]].append(schedule[1])
    except:
      times_per_person[schedule[0]] = [schedule[1]]

  edge_list = []
  source_vertex = "source"
  goal_vertex = "goal"

  all_persons = set()
  all_upstream = set()
  all_upstream_m = set()
  all_down_m = set()

  for meet, persons in persons_per_meeting.items():
    edge_list.append(( source_vertex, meet+"_m" ))
    edge_list.append(( meet+"_d", goal_vertex ))
    all_upstream_m.add(meet+"_m")
    all_down_m.add(meet+"_m")

    possible_times = set(times_per_person[persons[0]])
    for each_person in persons[1:]:
      possible_times = possible_times & set(times_per_person[each_person])

    for i in possible_times:
      edge_list.append(( meet+"_"+i, meet+"_d"))
      edge_list.append(( meet+"_m", meet+"_"+i+"_upstream" ))
      all_upstream.add(meet+"_"+i+"_upstream")
      for j in persons:
        all_persons.add(j+"_"+i)
        edge_list.append(( j+"_"+i, meet+"_"+i ))
        edge_list.append(( meet+"_"+i+"_upstream", j+"_"+i ))

  verticies = set()

  for edge in edge_list:
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

  for edge in list(set(edge_list)):
    sanitary_edge_list.append(( name_to_id[edge[0]], name_to_id[edge[1]] ))

  g = igraph.Graph(sanitary_edge_list,directed=True)
  g.vs["name"] = [id_to_name[v.index] for v in list(g.vs)]
  g.vs["label"] = g.vs["name"]

  g.es["capacity"] = None
  capacities = g.es["capacity"]

  i = 0
  for j in g.get_edgelist():
    if j[0] in set([name_to_id[x] for x in all_upstream_m]):
      capacities[i] = 1
    i += 1

  i = 0
  for j in g.get_edgelist():
    if j[0] in set([name_to_id[x] for x in all_down_m]):
      capacities[i] = 1
    i += 1

  i = 0
  for j in g.get_edgelist():
    if j[0] in set([name_to_id[x] for x in all_persons]):
      capacities[i] = 1
    i += 1

  i = 0
  for j in g.get_edgelist():
    if j[0] in set([name_to_id[x] for x in all_upstream]):
      capacities[i] = 0.25
    i += 1


  g.es["capacity"] = capacities

  flow = g.maxflow(name_to_id[source_vertex],name_to_id[goal_vertex],capacity="capacity")

  g.es["width"] = flow.flow

  print(flow.flow)

  layout = g.layout("kk")
  igraph.plot(g, "tmp.png", layout = layout)

#  print(meetings)
#  print(schedules)
