# !/usr/bin/env python3
import matplotlib.pyplot as plt
from elasticsearch import Elasticsearch
from matplotlib import rc
import json

deleted = []
live = []
names = []
r = []

# GET catalog/_segments?verbose=false&filter_path=indices.*.shards.0.segments

# es = Elasticsearch(hosts=[{'host': 'localhost', 'port': '9200'}])
# product_index = es.index(name='catalog', type='product')
# porduct_index.segments()
# es.forcemerge(index='...', max_num_segments=1, request_timeout=900)


i = 0
with open('shrads.json') as f:
    data = json.load(f)
    segments = data['segments']
    for segment_name in segments:
        segment_info = segments[segment_name]
        names.append(segment_name)
        live.append(segment_info['num_docs'])
        deleted.append(segment_info['deleted_docs'])
        r.append(i)
        i = i + 1

# y-axis in bold
rc('font', weight='bold')

# The position of the bars on the x-axis


# Names of group and bar width
barWidth = 1

# Create deleted bars
plt.bar(r, deleted, bottom=live, color='#557f2d', edgecolor='white', width=barWidth, label="deleted")
# Create live docs bars
plt.bar(r, live, color='#7f6d5f', edgecolor='white', width=barWidth, label='live')

# Custom X axis
plt.xticks(r, names, fontweight='bold')
plt.xlabel("group")
plt.legend(loc='upper right')
plt.xticks(rotation=70)

# Show graphic
plt.show()
