import numpy as np

CRS_METRIC = "EPSG:32612"                      # UTM 12N (Edmonton)
DEMO_BBOX = (-113.715, 53.335, -113.270, 53.720)  # (west, south, east, north): the City of Edmonton.
                                               # Changing it means rebuilding the graph and the exposure.
GRAPH_PAD_M = 300.0                            # the graph AND the incidents are loaded for DEMO_BBOX padded by this
WALK_SPEED_M_PER_MIN = 80.0                    # 4.8 km/h
DRIVE_FALLBACK_KMH = 40.0                      # posted-speed fallback; driving minutes are free-flow, no traffic
MIN_EDGE_MINUTES = 1e-3                        # no zero weights in csgraph
SNAP_MAX_M = 250.0
RADII_M = (50, 100, 200)
DEFAULT_RADIUS_M = 100
WINDOW_DAYS = 30                               # reports loaded for the map (its longest "Reported in" filter)
ROUTE_WINDOW_DAYS = 7                          # routes count only reports from this many days
ROUTE_WINDOW_PHRASE = f"last {ROUTE_WINDOW_DAYS} days"
N_DRAWS = 500
SEED = 20261106
DIRICHLET_KAPPA = 5.0
PRIOR_STRENGTH = 1.0                           # empirical-Bayes prior worth one window of reports (see A2.5)
PRIOR_NODE_MIN_GAP_M = 30.0                    # graph nodes farther than this from every published point become zero-count prior locations
LAMBDA_GRID = (0.0,) + tuple(float(x) for x in np.geomspace(0.05, 50.0, 11).round(4))  # minutes per attributed report, 12 values
MAX_EXTRA_TIME = 0.40                          # lower-exposure may be at most 40% slower than fastest
MIN_REDUCTION = 0.15                           # at least 15% lower than fastest ...
MIN_DRAW_SHARE = 0.90                          # ... in at least 90% of draws
MIN_REPORTS_FOR_SIGNAL = 1.0                   # below this the result is thin_data (sized for a 7-day window)
UNITS = f"reported incidents attributed to segments along this route, {ROUTE_WINDOW_PHRASE}"
# Walking routes use the walk pressure model (waykin/data/walk_pressure.py) over the same window the map shows.
WALK_HALF_LIFE_DAYS = 14.0                     # a report this old counts half as much as one from as_of
# Heavy spots dominate: a report's severity is squared (assault 9× a theft, homicide 25×), and the serious reports at
# one spot (assault, robbery, weapons, homicide) compound: their total is raised to WALK_SPOT_POWER, so a corner with
# several assaults outweighs the same assaults scattered along a route. Minor reports just add up.
WALK_SEVERITY_POWER = 2.0
WALK_SPOT_POWER = 1.5
WALK_SERIOUS_SEVERITY = 3.0
# No-go zones: a circle around every spot whose most serious report in the map window is at least this severe
# (homicide 5, weapons 3.5: the dark end of the dot colours). The lower-exposure route first keeps as much of its
# length out of these circles as the time cap allows, then minimises reports passed.
AVOID_MIN_SEVERITY = 3.5
AVOID_RADIUS_M = 100.0
AVOID_MINUTES_PER_M = 10.0                     # search penalty: a metre inside a zone costs as much as 10 minutes
WALK_SAMPLE_STEP_M = 10.0                      # points along each walkable edge for the closeness integral
WALK_WINDOW_PHRASE = f"last {WINDOW_DAYS} days"
WALK_UNITS = (f"incident score near this route, {WALK_WINDOW_PHRASE}; closer, more recent and more serious reports "
              "count more, and spots with several serious reports count far more")
UNITS_SHORT = "reported incidents"
DISCLAIMER = ("Counts of reported incidents near street segments, from public police data. "
              "They describe the past, not what will happen on your walk. "
              "Not for comparing neighbourhoods.")
RELAY_MAX_MSG_BYTES = 65536                    # route geometry can exceed 4 KB
RELAY_MAX_MSGS_PER_SEC = 4
RELAY_MAX_VIEWERS = 5
ROUTE_RESEND_EVERY = 10                        # the walker includes `route` in every Nth update, so late viewers get it
JOURNEY_TTL_MIN_DEFAULT = 120
JOURNEY_TTL_MIN_MAX = 240
WALKER_SILENT_S = 120                          # viewers get walker_silent after this long with no walker message
SESSION_TTL_DAYS = 14
INVITE_TTL_H = 24
FAMILY_MAX_MEMBERS = 8
LOGIN_ATTEMPTS_PER_MIN = 5
