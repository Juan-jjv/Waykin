import numpy as np

CRS_METRIC = "EPSG:32612"                      # UTM 12N (Edmonton)
DEMO_BBOX = (-113.535, 53.510, -113.480, 53.530)  # (west, south, east, north): U of A + Old Strathcona.
                                               # The team lead may change it before the H12 graph build. Never after.
GRAPH_PAD_M = 300.0                            # the graph AND the incidents are loaded for DEMO_BBOX padded by this
WALK_SPEED_M_PER_MIN = 80.0                    # 4.8 km/h
MIN_EDGE_MINUTES = 1e-3                        # no zero weights in csgraph
SNAP_MAX_M = 250.0
RADII_M = (50, 100, 200)
DEFAULT_RADIUS_M = 100
WINDOW_DAYS = 90
N_DRAWS = 500
SEED = 20261106
DIRICHLET_KAPPA = 5.0
PRIOR_STRENGTH = 1.0                           # empirical-Bayes prior worth one 90-day window (see A2.5)
PRIOR_NODE_MIN_GAP_M = 30.0                    # graph nodes farther than this from every published point become zero-count prior locations
LAMBDA_GRID = (0.0,) + tuple(float(x) for x in np.geomspace(0.05, 50.0, 11).round(4))  # minutes per attributed report, 12 values
MAX_EXTRA_TIME = 0.25                          # at most 25% slower than fastest
MIN_REDUCTION = 0.15                           # at least 15% lower than fastest ...
MIN_DRAW_SHARE = 0.90                          # ... in at least 90% of draws
MIN_REPORTS_FOR_SIGNAL = 3.0                   # below this the result is thin_data
BALANCED_MIN_REDUCTION = 0.05
UNITS = "reported incidents attributed to segments along this route, last 90 days"
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
