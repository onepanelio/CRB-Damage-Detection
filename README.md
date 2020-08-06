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


**Executing workflow using Python SDK**

You can install Onepanel SDK as follows: `pip3 install onepanel-sdk==0.12.0b2`.

You can execute Onepanel workflows using Onepanel's Python SDK. You can find sample script `workflow_execution.py` which shows how to execute workflow. This requires `ONEPANEL_AUTHORIZATION` envrionment variable. You can also directly use string (line #8) but that isn't recommended if you will be sharing this script with others. You can set that environment variable by editing `.bashrc` file as follows.

1 - `sudo ~/.bashrc`
2 - Add following line in the end.
    `export ONEPANEL_AUTHORIZATION=<onepanel-token-that-we-provided>`
3 - Save and exit `.bashrc` file.

Now that you have environment varibale set, you can go ahead and run the script. Feel free to modify script as you like. Currently, it takes video file and gps file path as an input. So you can run this script as follows.

`python3 workflow_execution.py <path-to-video-on-s3> <path-to-gps-csv-file-on-s3>`

You can pass other optional parameter as well. See commented line #24.
