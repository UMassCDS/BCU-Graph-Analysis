import random
import math
from scipy.stats import norm, lognorm 

#mean_length = 2414 refers to 1.5 miles roughly.
def choose_destination(origin_node, destination_nodes, G, rule="closest_only", beta=0.001, mean_length=2414, std_dev=2000):
    if not destination_nodes: return None

    orig_x, orig_y = G.nodes[origin_node]['x'], G.nodes[origin_node]['y']
    dests_with_dist = []
    for dest in destination_nodes:
        dest_x, dest_y = G.nodes[dest]['x'], G.nodes[dest]['y']
        dist = math.hypot(orig_x - dest_x, orig_y - dest_y)
        # Prevent division by zero or log errors
        dests_with_dist.append((dest, max(dist, 1.0))) 

    if rule == "closest_only":
        dests_with_dist.sort(key=lambda x: x[1])
        return dests_with_dist[0][0]

    weights = []
    dest_list = []
    
    if rule == "lognormal":
        for dest, dist in dests_with_dist:
            weight = lognorm.pdf(dist, s=std_dev, scale=mean_length) 
            weights.append(weight)
            dest_list.append(dest)

    if not weights:
        return random.choice(destination_nodes)

    return random.choices(dest_list, weights=weights, k=1)[0]