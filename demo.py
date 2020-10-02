import os
import tensorflow as tf
# uncomment following lines if you are using TF2
# import tensorflow.compat.v1 as tf
# tf.disable_v2_behavior() 
import numpy as np
import json
import ast
import cv2
import argparse
from PIL import Image
# from gpslogger import GPSLogger
import math
import sys
sys.path.append(os.environ.get('AUTO_SEGMENTATION_PATH')) 
from mrcnn.config import Config
import mrcnn.model as modellib
import time
import skimage.io
from collections import OrderedDict
from skimage.measure import find_contours, approximate_polygon
from xml_dumper import dump_as_cvat_annotation
from sql_dumper import dump_to_sql

class ObjectDetection:
    def __init__(self, model_path):
        self.detection_graph = tf.Graph()
        with self.detection_graph.as_default():
            od_graph_def = tf.GraphDef()
            with tf.gfile.GFile(model_path , 'rb') as fid:
                serialized_graph = fid.read()
                od_graph_def.ParseFromString(serialized_graph)
                tf.import_graph_def(od_graph_def, name='')
                config = tf.ConfigProto()
                config.gpu_options.allow_growth=True
                self.sess = tf.Session(graph=self.detection_graph, config=config)

    def get_detections(self, image_np_expanded):
        image_tensor = self.detection_graph.get_tensor_by_name('image_tensor:0')
        boxes = self.detection_graph.get_tensor_by_name('detection_boxes:0')
        scores = self.detection_graph.get_tensor_by_name('detection_scores:0')
        classes = self.detection_graph.get_tensor_by_name('detection_classes:0')
        num_detections = self.detection_graph.get_tensor_by_name('num_detections:0')
        (boxes, scores, classes, num_detections) = self.sess.run([boxes, scores, classes, num_detections], feed_dict={image_tensor: image_np_expanded})
        return boxes, scores, classes, num_detections

    @staticmethod
    def process_boxes(boxes, scores, classes, labels_mapping, threshold, width, height):
        result = {}
        for i in range(len(classes[0])):
            if classes[0][i] in labels_mapping.keys():
                if scores[0][i] >= threshold:
                    xmin = int(boxes[0][i][1] * width)
                    ymin = int(boxes[0][i][0] * height)
                    xmax = int(boxes[0][i][3] * width)
                    ymax = int(boxes[0][i][2] * height)
                    label = labels_mapping[classes[0][i]]
                    if label not in result:
                        result[label] = []
                    result[label].append([xmin,ymin,xmax,ymax])
        return result

class Segmentation:
    def __init__(self, model_path, num_c=2):
        class InferenceConfig(Config):
            # Set batch size to 1 since we'll be running inference on
            # one image at a time. Batch size = GPU_COUNT * IMAGES_PER_GPU
            NAME = "cvat"
            GPU_COUNT = 1
            IMAGES_PER_GPU = 1
            NUM_CLASSES = num_c

        config = InferenceConfig()
        #config.display()

        # Create model object in inference mode.
        self.model = modellib.MaskRCNN(mode="inference", model_dir="./output", config=config)
        # Load weights trained on MS-COCO
        self.model.load_weights(model_path, by_name=True)
        self.labels_mapping = {0:'BG', 1:'cut'}
        self.contour_count = 0 # count empty controus for debugging
    
    def get_polygons(self, images, threshold):
        res = self.model.detect(images)
        result = {}
        for r in res:
            for index, c_id in enumerate(r['class_ids']):
                if c_id in self.labels_mapping.keys():
                    if r['scores'][index] >= threshold:
                        mask = r['masks'][:,:,index].astype(np.uint8)
                        contours = find_contours(mask, 0.5)
                        if not contours:
                            self.contour_count += 1
                            continue
                        contour = contours[0]
                        contour = np.flip(contour, axis=1)
                        contour = approximate_polygon(contour, tolerance=2.5)
                        segmentation = contour.ravel().tolist()
                        label = self.labels_mapping[c_id]
                        if label not in result:
                            result[label] = []
                        result[label].append(segmentation)
        return result
    
    
    @staticmethod
    def process_polygons(polygons, boxes):
        """
           Check if any point of the polygon falls into any of coconot palms except for dead/non_recoverable.
        """
        def _check_inside_boxes(polygon, boxes):
            for point in polygon:
                for label, bxes in boxes.items():
                    for box in bxes:
                        if point[0] > box[0] and point[0] < box[2] and point[1] > box[1] and point[1] < box[3] and label not in ['dead','non_recoverable']:
                            # point is inside rectangle
                            return True
            return False
    
        result = {}
        for label_m, polys in polygons.items():
            for polygon in polys:
                p = [polygon[i:i+2] for i in range(0, len(polygon),2)]
                if _check_inside_boxes(p, boxes):
                    if label_m not in result:
                        result[label_m] = []
                    result[label_m].append(polygon)
                
        return result


def load_image_into_numpy(image):
    (im_width, im_height) = image.size
    return np.array(image.getdata()).reshape((im_height, im_width, 3)).astype(np.uint8)

def draw_instances(frame, boxes, masks):
    colors = {'zero':(0,255,0), 'light':(0,0,255),'medium':(255,0,0),'high':(120,120,0),'non_recoverable':(0,120,120),'cut':(0,0,0)}
    #draw boxes
    for label, bxes in boxes.items():
        for box in bxes:
            cv2.rectangle(frame, (box[0],box[1]), (box[2],box[3]), colors[label], 5)
    #draw polygons
    for label, polygons in masks.items():
        for polygon in polygons:
            p = [polygon[i:i+2] for i in range(0, len(polygon),2)]
            pts = np.array(p, np.int32)
            pts = pts.reshape((-1,1,2))
            cv2.polylines(frame, [pts], True, (0,255,255),5)
    return frame

def get_labels(classes_csv, type="od"):
    labels = []
    with open(classes_csv, "r") as f:
        data = f.readlines()
        # slogger.glob.info("class file data {}".format(data))
        for line in data[1:]:
            if type == "maskrcnn":
                if "," not in line:
                    continue
                # slogger.glob.info("classes line {}".format(line))
                label, num = line.strip().split(',')
                labels.append(('label', [('name', line.strip())]))
            else:
                if "label" not in line:
                    labels.append(('label', [('name', line.strip())]))
    return labels
    
def main(args):
    if args.type == "both":
        od_model = ObjectDetection(args.od_model)
        seg_model = Segmentation(args.mask_model)
    elif args.type == "classes":
        od_model = ObjectDetection(args.od_model)
    elif args.type == "v_shape":
        seg_model = Segmentation(args.mask_model)
       
    print("File Exists: ", os.path.exists("/mnt/data/datasets/temp.mp4"))
    print("File Size: ", os.path.getsize("/mnt/data/datasets/temp.mp4"))
    cap = cv2.VideoCapture("/mnt/data/datasets/temp.mp4")
    #would be better to take csv files as an input
    #labels_mapping_od = {1:'dead', 2:'damaged',3:'healthy'}
    labels_mapping_od = {1:'zero',2:'light',3:'medium',4:'high',5:'non_recoverable'}
    frame_no = 0 
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = math.ceil(cap.get(cv2.CAP_PROP_FPS))
    num_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if args.num_frames == 'None' or args.num_frames == None:
        args.num_frames = num_frames
    out = cv2.VideoWriter(os.path.join("/mnt/output/", os.path.basename(args.video)[:-4]+"_skip_{}_numframes_{}.mp4".format(args.skip_no, args.num_frames)), fourcc, fps, (frame_width,frame_height))
   
    
    labels_from_csv = get_labels(args.classes_cvat, args.classes_type)
    print("Labels: ", labels_from_csv)
    final_result = {'meta':{'task': OrderedDict([('id',str(args.task_id)),('name',str(args.task_name)),('size',str(num_frames)),('mode','interpolation'),('start_frame', str(0)),('stop_frame', str(num_frames-1)),('z_order',"False"),('labels', labels_from_csv)])}, 'frames':[]}
    
    output_xml_path = "/mnt/output/cvat_annotation_"+os.path.basename(args.video)[:-4]+"_skip_{}_numframes_{}.xml".format(args.skip_no, args.num_frames)
    while True:
        ret, frame = cap.read()
        if ret:
            if frame_no % args.skip_no != 0:
                frame_no += 1
                continue
            print("Processing frame: ", frame_no)
            # get image ready for inference
            img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image_org = Image.fromarray(img)
            image_mask_rcnn = np.array(image_org)
            width, height = image_org.size
            if width > 1920 or height > 1080:
                image_org = image_org.resize((width // 2, height // 2), Image.ANTIALIAS)
            image_np = np.array(image_org)
            image_np_expanded = np.expand_dims(image_np, axis=0)
           
            od_result = {}
            result = {}
            if args.type == "both" or args.type == "classes":
                # run detection
                boxes, scores, classes, num_detections = od_model.get_detections(image_np_expanded)
                #normalize bounding boxes, also apply threshold
                od_result = ObjectDetection.process_boxes(boxes, scores, classes, labels_mapping_od, args.od_threshold, width, height)
                if od_result:
                    print("Object Detection:", od_result)
                    shapes = []
                    for label, boxes in od_result.items():
                        for box in boxes:
                            shapes.append({'type':'rectangle','label':label,'occluded':0,'points':box})
                    final_result['frames'].append({'frame':frame_no, 'width':frame_width, 'height':frame_height, 'shapes':shapes})
            
            if args.type == "both" or args.type == "v_shape":
                # run segmentation
                result = seg_model.get_polygons([image_mask_rcnn], args.mask_threshold)
                print("Result without processing: ", result)
                if args.type == "both" or args.type == "classes":
                    # filter out false positives if boxes are available
                    result = Segmentation.process_polygons(result, od_result)
                print("Result: ", result)
                if result:
                    shapes = []
                    for label, polygons in result.items():
                        for polygon in polygons:
                            shapes.append({'type':'polygon','label':label,'occluded':0,'points':polygon})
                    frame_exists = False
                    for frame_ in final_result['frames']:
                        if frame_['frame'] == frame_no:
                            break
                    if frame_exists:
                        final_result['frames']['shapes'].extend(shapes)
                    else:
                        final_result['frames'].append({'frame':frame_no, 'width':frame_width, 'height':frame_height, 'shapes':shapes})            
            frame = draw_instances(frame, od_result, result)
            #write video
            out.write(frame)

            if (frame_no // args.skip_no) + 1 == int(args.num_frames):
                dump_as_cvat_annotation(open(output_xml_path,"w"), final_result)
                cap.release()
                out.release()
                break
            frame_no += 1
           
        else:
            try:
             
                print("Final result: ", final_result)
                print("Empty controus: ", seg_model.contour_count)
                dump_as_cvat_annotation(open(output_xml_path, "w"), final_result)
                cap.release()
                out.release()
                break
            except:  #handle case when video is corrupted or does not exists
                break

    return output_xml_path, args.num_frames

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--type",default="both",help="what type of models to use [both,classes,v_shape]")
    parser.add_argument("--video", default="/mnt/data/datasets/temp.mp4", help="path to video")
    parser.add_argument("--gps_csv", default="/home/savan/Downloads/20200703_124043_gps.csv", help="path to csv containing gps data")
    parser.add_argument("--skip_no", default=7, type=int, help="num of frames to skip")
    parser.add_argument("--num_frames", default=None, help="how many frames to consider?")
    parser.add_argument("--od_model", default="/mnt/data/od-models/frozen_inference_graph.pb" , help="path to trained detection model")
    parser.add_argument("--classes_cvat", default="/mnt/data/datasets/classes.csv", help="classes you want to use for cvat, see readme for more details.")
    parser.add_argument("--classes_type", default="od", help="type of classes csv file [od, maskrcnn]")
    parser.add_argument("--mask_model", default="/mnt/data/mask-models/mask_rcnn_cvat.h5", help="path to trained maskrcnn model")
    parser.add_argument("--od_threshold",type=float, default=0.5, help="threshold for IoU")
    parser.add_argument("--mask_threshold",type=float, default=0.5, help="threshold for maskrcnn")
    parser.add_argument("--output_video", default="/mnt/output/output.mp4", help="where to store output video")
    parser.add_argument("--survey_type", default="v_shape",help="what to write in geojson [v_shape,classes")
    parser.add_argument("--task_id", default=0, type=int, help="required only if you want to use this in cvat")
    parser.add_argument("--task_name", default="demo", help="requierd only if you want to use this in cvat")
    parser.add_argument("--write_into_objects", default=True, help="should this enter detected objects into objects table?")
    parser.add_argument("--drop_extra_clm", default=True, help="whether it should drop extra columns? required if dumping into objects table")
    # have to use string as we cant have condition statements in workflow
    parser.add_argument('--dump_sql', default='true')
    args = parser.parse_args()
    if args.type not in ['both','classes','v_shape']:
        raise ValueError('Invalid type: {}. Valid options are "both","classes","v_shape".'.format(args.type))
    # if not os.path.exists(args.video):
    #     raise FileExistsError("Video does not exist!")
    start_time = time.time()
    output_xml_path, num_frames_ = main(args)
    print("Time took to run inference: {}".format(time.time() - start_time))
    if args.dump_sql == "true":
        dump_to_sql(output_xml_path, "/mnt/data/datasets/gps.csv", os.path.basename(args.video), args.skip_no, args.write_into_objects, args.drop_extra_clm, int(num_frames_))
