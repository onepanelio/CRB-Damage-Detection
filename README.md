## Running Inference using Multiple Models

`demo.py` runs inference on given input video and outputs video with bounding boxes/polygons drawn.

**Install dependecies:**
Works on linux system only.
```shell
./setup.sh
```


**Install prerequisites:**
```python
pip3 install -r requirements.txt
```

**Run demo:**
```python
python3 demo.py --type=both \ 
    --video=demo.mp4 \                         #path to input video
    --gps_csv=demo.csv \                       #path to csv file containing gps data
    --od_model=frozen_inference_graph.pb \     #path to frozen graph for object detection
    --mask_model=mask_rcnn_cvat.h5 \           #path to maskrcnn model
    --output_video=output.mp4  \               #path to output video
    --skip_no=7  \                             #number of frames to skip
    --num_frames=None  \                       #number of frames to process, None for all
    --dump_sql=True  \                         #should data be dumped into sql database
    --write_into_objects=True  \               #should objects be dumped into `objects` table
    --drop_extra_clm=True   \                  #need to be true if you are dumping into `objects` table
                             
```

Notes:

- If you are planning to dump the XML file into CVAT, then make sure you pass in correct `--task_id` and `--task_name` so that you can upload this into CVAT.
- You also need to provide a csv file `--classes_cvat`, if you are planning to use this XML file in CVAT. Since object detection and MaskRCNN model can have different classes, make sure you use file which has same classes as your CVAT task (where you are planning to upload this XML file).
- This will work with tasks that were created for videos only. Since tasks with images will have different names. 