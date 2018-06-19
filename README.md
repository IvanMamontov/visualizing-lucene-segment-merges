Origin is https://github.com/mikemccand/luceneutil/blob/master/src/python/mergeViz.py
Read about it at http://blog.mikemccandless.com/2011/02/visualizing-lucenes-segment-merges.html

It parses the infoStream output from IndexWriter, renders one frame at a time, saved as a PNG file in the local file system,
using the Python Imaging Library, and finally encodes all frames into a video using MEncoder with the X264 codec.

The main changes are:
* replatformed to python3
* rewritten Image processing
