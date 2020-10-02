import pandas as pd
import xml.etree.ElementTree as ET
import csv
import os
import sys
from sqlalchemy import create_engine


def str2int(s):
    return int(float(s))
  
    
def dump_to_sql(xml_file, gps_csv, video_file, skip_no, write_into_objects, drop_extra, num_frames):
    user = os.getenv('CRB_SQL_USERNAME')
    password = os.getenv('CRB_SQL_PASSWORD')

    root = ET.parse(xml_file).getroot()
    engine, connection = connect_to_db(user, password)
    add_frames(root, engine, video_file, gps_csv, skip_no, num_frames)
    add_trees(root,engine, video_file)
    add_vcuts(root, engine, video_file)

def connect_to_db(username, password):
    engine = create_engine('mysql+pymysql://{}:{}@mysql.guaminsects.net/videosurvey'.format(username, password))
    connection = engine.connect()
    return engine, connection

def add_frames(root, engine, video_id, gps_csv, skip_no, num_frames):
    """
    Extracts frame data from CVATXMLFILE and appends this to the frames table in the videosurvey MySQL database.
    This code will fail if identical records already exist in the frames table or 
    if the videos table does not contain corresponding video_ids.   
    """
    image_id_set = set()
    for image in root.findall('image'):
        image_id_set.add(int(image.attrib['id']))
    if not image_id_set:
        # exit if no trees are detected
        print("Exiting sql dumping since no objects were detected...")
        sys.exit(0)
    mylist = sorted(list(image_id_set))
    df = pd.DataFrame(mylist, columns=['frame'])
    df['video_id'] = video_id
    df['frame_id'] = df.frame.apply(lambda x: '{}-{}'.format(video_id, x))
    # df = df.merge(pd.read_csv(gps_csv))
    df_gps = pd.read_csv(gps_csv)
    df_gps = df_gps.iloc[0:skip_no*num_frames-skip_no+2:skip_no]
    df = df.merge(df_gps)
    df = df[['frame_id','video_id','frame','timestamp','lat','lon']]
    df.to_sql('frames', engine, index=False, if_exists='append')


def add_trees(root, engine, video_id):
    """
    Extracts tree image data from CVATXMLFILE and appends this to the trees table in the videosurvey MySQL database.
    This code will fail if identical records already exist in the trees table or 
    if the frames table does not contain corresponding frame_ids.   
    """
    mylist = []
    for image in root.findall('image'):
        for box in image.findall('box'):
            mydict = box.attrib
            mydict.update(image.attrib)
            mylist.append(mydict)
    df = pd.DataFrame(mylist)
    df = df[(df.occluded=='0')]
    damagedict = {'zero':0, 'light':1, 'medium':2, 'high':3, 'non_recoverable':4}
    df['damage'] = df.label.apply(lambda x: damagedict[x])
    df['frame_id'] = df.id.apply(lambda x: '{}-{}'.format(video_id, x))
    df.xbr = df.xbr.apply(lambda x: str2int(x))
    df.xtl = df.xtl.apply(lambda x: str2int(x))
    df.ybr = df.ybr.apply(lambda x: str2int(x))
    df.ytl = df.ytl.apply(lambda x: str2int(x))
    df = df[['frame_id', 'damage', 'xtl', 'ytl', 'xbr', 'ybr']]
    df.to_sql('trees', engine, index=False, if_exists='append')

def add_vcuts(root, engine, video_id):
    """
    Extracts vcut image data from CVATXMLFILE and appends this to the vcuts table in the videosurvey MySQL database.
    This code will fail if identical records already exist in the vcuts table or 
    if the frames table does not contain corresponding frame_ids.   
    """
    mylist = []
    for image in root.findall('image'):
        for poly in image.findall('polygon'):
            mydict = poly.attrib
            mydict.update(image.attrib)
            mylist.append(mydict)
    df = pd.DataFrame(mylist)
    df = df[(df.occluded=='0')]
    df.rename(mapper={'points':'poly_json'}, inplace=True, axis='columns')
    df['frame_id'] = df.id.apply(lambda x: '{}-{}'.format(video_id, x))
    df = df[['frame_id', 'poly_json']]
    df.to_sql('vcuts', engine, index=False, if_exists='append')


# for development
if __name__ == "__main__":
    xml_file = sys.argv[1]
    gps_csv = sys.argv[2]
    video_file = sys.argv[3]
    skip_no = 7
    video_file = "20200625_125121.mp4"
    write_into_objects = True
    num_frames = 10
    root = ET.parse(xml_file).getroot()
    engine, connection = connect_to_db(os.getenv('CRB_SQL_USERNAME'), os.getenv('CRB_SQL_PASSWORD'))
    add_frames(root, engine, video_file, gps_csv, skip_no, num_frames)
    add_trees(root,engine, video_file)
    add_vcuts(root, engine, video_file)
    
    # sample command
    # python3 sql_dumper.py /home/savan/Downloads/cvat_annotation_20200703_124043_skip_7_numframes_10.xml \
    #                     /home/savan/Downloads/20200703_124043_gps.csv \
    #                     /home/savan/Downloads/20200703_124043.mp4      \                    
