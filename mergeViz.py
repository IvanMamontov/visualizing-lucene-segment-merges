#!/usr/bin/env python3

# Licensed to the Apache Software Foundation (ASF) under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Origin is https://github.com/mikemccand/luceneutil/blob/master/src/python/mergeViz.py
# Read about it at http://blog.mikemccandless.com/2011/02/visualizing-lucenes-segment-merges.html

import argparse
import math
import os
import re
import subprocess

from datetime import datetime
# You need Pillow for this: http://pillow.readthedocs.io/en/stable/
from PIL import Image, ImageDraw, ImageFont
from tempfile import TemporaryDirectory

"""
Parses infoStream output from IW and draws an movie showing the merges over time.
"""

WIDTH = 1280
HEIGHT = 720
MAX_SEG_COUNT = 60
MAX_SEG_SIZE_MB = 500.0
LIMIT = None
LOG_BASE_MB = 10.0
LOG_BASE = math.log(LOG_BASE_MB)
FPS = 24

FONT = ImageFont.load_default()

MERGE_COLORS = (
    '#ffccff',
    '#ffff99',
    '#ccff99',
    '#ff9900',
    '#00ccff',
    '#33ffcc',
    '#9999ff',
    '#fbff94',
    '#cbff94',
    '#fb9904',
    '#0bccf4',
    '#3bffc4',
    '#9b99f4',
)


def parse_time(l, timeformat):
    m = reTime.search(l)
    # Expects these datetimes: 07 Jul 12:54:12.554
    dt = datetime.strptime(m.group(1), timeformat)
    return dt.timestamp()


def main(log_files, output_file, temp_directory, timeformat):
    global MAX_SEG_COUNT
    global MAX_SEG_SIZE_MB

    merges, segToFullMB = parse(log_files, timeformat)

    MAX_SEG_COUNT = 1
    MAX_SEG_SIZE_MB = 0.0
    for i, ev in enumerate(merges):
        if ev[0] == 'index':
            segs = ev[2]
            MAX_SEG_COUNT = max(MAX_SEG_COUNT, len(segs))
            for seg, mb, delPct in segs:
                MAX_SEG_SIZE_MB = max(MAX_SEG_SIZE_MB, mb)

    MAX_SEG_COUNT += 2
    MAX_SEG_SIZE_MB = 100 * math.ceil((MAX_SEG_SIZE_MB * 1.1) / 100.0) + 50.0

    print('MAX seg MB %s' % MAX_SEG_SIZE_MB)
    print('%d events' % len(merges))

    mergeToColor = {}
    segToMBAndDel = {}
    segs = None
    upto = 0
    totMergeMB = 0
    newestSeg = ''
    minT = None
    for i, ev in enumerate(merges):
        t = ev[1]
        if minT is None:
            minT = t

        print('%s: %s/%s' % (t - minT, i, len(merges)))

        if ev[0] == 'index':
            segs = ev[2]
            for seg, fullMB, delPCT in segs:
                if seg not in segToMBAndDel:
                    newestSeg = seg
                segToMBAndDel[seg] = (fullMB, delPct)
            if i < len(merges) - 1 and merges[1 + i][0] == 'merge':
                continue
        elif ev[0] == 'merge':
            seen = set()
            for seg, color in mergeToColor.items():
                seen.add(color)
            for color in MERGE_COLORS:
                if color not in seen:
                    for seg in ev[2]:
                        totMergeMB += segToFullMB[seg] * (2.0 - segToMBAndDel[seg][1])
                        mergeToColor[seg] = color
                    break
            else:
                raise RuntimeError('ran out of colors')
        else:
            raise RuntimeError('unknown event %s' % ev[0])

        img, mergeToColor = draw(t, segs, mergeToColor, newestSeg, totMergeMB)
        img.save('%s/%08d.png' % (temp_directory, upto))
        upto += 1
        if LIMIT is not None and upto >= LIMIT:
            break

    cmd = ['mencoder',
           'mf://%s/*.png' % temp_directory,
           '-mf',
           'type=png:w=%s:h=%s:fps=%s' % (WIDTH, HEIGHT, FPS),
           '-ovc',
           'lavc',
           '-lavcopts',
           'vcodec=mjpeg',
           '-oac',
           'copy',
           '-o',
           '%s' % output_file]
    subprocess.call(cmd)
    print('DONE')


tMin = None


def draw(t, segs, mergeToColor, rightSegment, totMergeMB):
    global tMin
    if tMin is None:
        tMin = t

    i = Image.new('RGB', (WIDTH, HEIGHT), 'white')

    segsAlive = set([s[0] for s in segs])
    # print 'alive: %s' % segsAlive

    newMergeToColor = {}
    for seg, color in mergeToColor.items():
        if seg in segsAlive:
            newMergeToColor[seg] = color

    maxLog = math.log(LOG_BASE_MB + MAX_SEG_SIZE_MB) - LOG_BASE
    yPerLog = (HEIGHT - 20) / maxLog

    xPerSeg = int(WIDTH / MAX_SEG_COUNT)

    d = ImageDraw.Draw(i)

    for sz in (10.0, 50.0, 100.0, 500.0, 1024, 5 * 1024):
        y = HEIGHT - 10 - yPerLog * (math.log(LOG_BASE_MB + sz) - LOG_BASE)
        d.line(((0, y), (WIDTH, y)), fill='#cccccc')
        if sz >= 1024:
            s = '%d GB' % (sz / 1024)
        else:
            s = '%d MB' % sz
        d.text((WIDTH - 80, y - 20), s, fill='black', font=FONT)

    totMB = 0
    mergingMB = 0
    for idx, (seg, mb, delPct) in enumerate(segs):
        totMB += mb * (1.0 - delPct)
        x0 = idx * (xPerSeg) + 1
        x1 = x0 + xPerSeg - 2
        y0 = HEIGHT - 10 - yPerLog * (math.log(LOG_BASE_MB + mb) - LOG_BASE)
        y1 = HEIGHT - 10

        if seg in mergeToColor:
            fill = mergeToColor[seg]
            mergingMB += mb
        else:
            fill = '#dddddd'

        d.rectangle(((x0, y0), (x1, y1)), outline='black', fill=fill)

        if delPct > 0.0:
            y2 = y0 + (y1 - y0) * delPct
            d.rectangle(((x0, y0), (x1, y2)), outline='black', fill='gray')

    baseY = HEIGHT - 10 - yPerLog * (math.log(LOG_BASE_MB + 500) - LOG_BASE) + 15
    baseX = WIDTH - 220

    d.text((baseX, baseY), '%d sec' % (t - tMin), fill='black', font=FONT)

    if totMB < 1024:
        sz = '%4.1f MB' % totMB
    else:
        sz = '%4.2f GB' % (totMB / 1024.)
    d.text((baseX, 20 + baseY), '%s' % sz, fill='black', font=FONT)

    d.text((baseX, 40 + baseY), '%d segs; %s' % (len(segs), rightSegment), fill='black', font=FONT)

    if mergingMB < 1024:
        sz = '%.1f MB' % mergingMB
    else:
        sz = '%.2f GB' % (mergingMB / 1024.)
    d.text((baseX, 60 + baseY), '%s merging' % sz, fill='black', font=FONT)

    if totMergeMB >= 1024:
        s = '%4.2f GB' % (totMergeMB / 1024)
    else:
        s = '%4.1f MB' % totMergeMB

    d.text((baseX, 80 + baseY), '%s merged' % s, fill='black', font=FONT)

    return i, newMergeToColor


reSeg1 = re.compile(r'\*?(_.*?)\(.*?\):[cC]v?([0-9]+)(/[0-9]+)?')
reSeg2 = re.compile(r'seg=\*?(_.*?)\(.*?\):[cC]v?([0-9]+)(/[0-9]+)? .*?size=([0-9.]+) MB')
reTime = re.compile(r'^(.*?) +[A-Z]+ +')


def parse(log_files, timeformat):
    events = []
    segs = []
    segsToFullMB = {}

    for log_file in log_files:
        with open(log_file, 'r') as f:
            for l in f.readlines():
                if l == '':
                    break
                i = l.find('seg=')
                if i != -1:
                    l = l[i:]
                    m2 = reSeg2.search(l)
                    if m2 is not None:
                        seg = m2.group(1)
                        # print 'matches %s' % str(m2.groups())
                        del_count = m2.group(3)
                        if del_count is not None:
                            del_count = int(del_count[1:])
                        else:
                            del_count = 0
                        docCount = int(m2.group(2))

                        undelSize = float(m2.group(4))
                        if seg not in segsToFullMB:
                            if del_count != 0:
                                del_ratio = float(del_count) / docCount
                                if del_ratio < 1.0:
                                    full_size = undelSize / (
                                                1.0 - del_ratio)
                                else:
                                    # total guess!
                                    print('WARNING: total guess!')
                                    full_size = 0.1
                            else:
                                full_size = undelSize
                            segsToFullMB[seg] = full_size

                        # seg name, fullMB, delPct
                        assert del_count <= docCount, 'docCount %s delCount %s line %s' % (
                        docCount, del_count, l)
                        segs.append((seg, segsToFullMB[seg],
                                     float(del_count) / docCount))
                        continue

                if segs and (l.find('allowedSegmentCount=') != -1 or l.find('LMP:   level ') != -1):
                    events.append(('index', t, segs))
                    segs = []
                    continue

                i = l.find('   add merge=')
                if i != -1:
                    t = parse_time(l, timeformat)
                    l = l[i:]
                    merged = []
                    for tup in reSeg1.findall(l):
                        seg = tup[0]
                        merged.append(seg)
                    events.append(('merge', t, merged))
                    continue

                if l.find(': findMerges: ') != -1:
                    t = parse_time(l, timeformat)
                    if segs:
                        events.append(('index', t, segs))
                    segs = []
                    continue

    return events, segsToFullMB


def find_log_files(base_name):
    files = [base_name]
    i = 1

    while True:
        n = "{}.{}".format(base_name, i)
        if not os.path.isfile(n):
            break
        files.append(n)
        i += 1

    return list(reversed(files))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Parses infoStream output from IW and draws an movie showing the merges over time."
    )
    parser.add_argument('log_file', type=str, help='Log file or pattern')
    parser.add_argument('output_file', type=str, help='Output mov file')
    parser.add_argument('--timeformat', type=str, default='%Y-%m-%d %H:%M:%S.%f', nargs='?',
                        help='Time format, by default uses %d %b %H:%M:%S.%f which expects 07 Jul 12:54:12.554',
                        required=False)

    args = parser.parse_args()

    log_files = find_log_files(args.log_file)
    for file in log_files:
        print('Found {}'.format(file))

    with TemporaryDirectory(prefix="mergeimages-") as temp_directory:
        main(log_files, args.output_file, temp_directory, args.timeformat)