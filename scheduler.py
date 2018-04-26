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

if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  parser.add_argument('--meetings',required=True,type=str)
  parser.add_argument('--schedules',required=True,type=str)
  args = parser.parse_args()

  with open(args.meetings,"r") as f:
    meetings = list(csv.reader(f))[1:]
  with open(args.schedules,"r") as f:
    schedules = list(csv.reader(f))[1:]

  rooms = ["r1","r2"]

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
  all_personBYtime = set()
  all_meetingBYtime = set()
  all_roomsBYtime = set()

  for person, times in times_per_person.items():
    all_persons.add(person)
    edge_list.append(( source_vertex, person ))
    for t in times:
      edge_list.append(( person, person+"_"+t ))
      all_personBYtime.add(person+"_"+t)

  for meet, persons in persons_per_meeting.items():

    possible_times = set(times_per_person[persons[0]])
    for each_person in persons[1:]:
      possible_times = possible_times & set(times_per_person[each_person])
    print(possible_times)

    for t in possible_times:
      all_meetingBYtime.add(meet+"_"+t)
      for p in persons:
        edge_list.append(( p+"_"+t, meet+"_"+t ))
      for r in rooms:
        edge_list.append(( meet+"_"+t, r+"_"+t ))
        edge_list.append(( r+"_"+t, goal_vertex ))
        all_roomsBYtime.add(r+"_"+t)

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

  g.es["capacity"] = 1000
  capacities = g.es["capacity"]

  i = 0
  for j in g.get_edgelist():
    if j[0] in set([name_to_id[x] for x in all_personBYtime]):
      capacities[i] = 1
    if j[0] in set([name_to_id[x] for x in all_meetingBYtime]):
      capacities[i] = len(g.incident(j[0],mode="IN"))
#    if j[0] in set([name_to_id[x] for x in all_roomsBYtime]):
#      capacities[i] = 1
    i += 1

  print(list(zip([id_to_name[x]+" -> "+id_to_name[y] for x,y in g.get_edgelist()],capacities)))

  g.es["capacity"] = capacities

  flow = g.maxflow(name_to_id[source_vertex],name_to_id[goal_vertex],capacity="capacity")

  g.es["width"] = flow.flow

  print(flow.flow)

  layout = g.layout("fr")
  igraph.plot(g, "tmp.png", layout = layout, 
    edge_width=[0.1+2*width for width in g.es["width"]])

#  print(meetings)
#  print(schedules)
