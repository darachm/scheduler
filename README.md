This is for scheduling meetings with arbitrary sets of people with
arbitrary schedules, in certain windows of time. 

Early attempts were using maximum flows on graphs, but that doesn't seem to work
since you can restrict the occurances of a meetings with capacities but that 
just allows partial meetings to happen at different times.
Nonlinear costs don't seem to be a solved problem for min-cost max-flows.

So instead, the current solution is just to enumerate all possible schedules of
meetings of a certain resolution. If there's a conflict of rooms or person's
availability, it fails. If not, then it returns the schedule as an ical in the
output directory.

# Usage:

    python3 scheduler.py --meetings meetings.csv --rooms rooms --people people --resolution 30 --output-dir output

If you add `--debug`, you get a ton of poorly documented data dumps and a 
blow-by-blow narration of the failed (and successful) schedules.

# Format

See the tracked files in `people` and `rooms`, and the `meetings.csv` file for
example formats. Basically, it's an ical file for each room and person, and
a CSV for the meetings that tells us the id, the duration, and the participants.
That first bit before the `@` in the file name on the icals has to match.
