1. 复制（删除）path2中与path1相同的文件，保存到save_path

```python
import os
import shutil
#复制path2中与path1相同的文件，保存到save_path
data1_path = '/Users/dushuai/Desktop/0714_error/'
data2_path = '/Users/dushuai/Desktop/后处理/0.29_101_0714_lr0.2_60/'
save_path = '/Users/dushuai/Desktop/后处理/'


file1_list = os.listdir(data1_path)
for file in file1_list:
    a = file.split('.')
    #a_boxed = 'boxed_' + a[0]     #如果有前缀，需要去除
    test_list.append(a[0])
    
if not os.path.exists(save_path):  #创建save_path 
    os.makedirs(save_path)
    
file2_list = os.listdir(data2_path)
test_list = []
for i in file2_list:
    num = (i.split('.'))[0]
    if num in test_list:
        # 当文件数超过1个时才复制或删除
        # if test_list.count(num) > 1:
        shutil.copy(os.path.join(data2_path, i), save_path)   #复制图片
        #os.remove(os.path.join(data2_path, i))               #删除图片
    else:
        continue
```

2. 删除含有特定字符的文件

```python
import os

data1_path = '/Users/dushuai/Desktop/111/'
file1_list = os.listdir(data1_path)

for file in file1_list:
		#newname = file[6:]
    #os.rename(data1_path + file, data1_path + newname)  #批量重命名文件
    a = file.split('.')
    print(a[0])
    if a[0][-2:] == '_b':      #删除末尾含有'_b'的文件
        os.remove(os.path.join(data1_path, file))
```


3. 图片转格式（更改文件后缀）
```python
import PIL.Image
import os
import cv2
i=0

path = ""
savepath = ""

#去除mac下的隐藏文件
filelist = os.listdir(path)
for item in filelist:
        if item.startswith('.') and os.path.isfile(os.path.join(path, item)):
            filelist.remove(item)

#opencv更改
for file in filelist:
    img_OpenCV = cv2.imread(path + file)
    a = file.split('.')
    filename = a[0] + '.png'
    cv2.imwrite(savepath + filename, img_OpenCV)
#PIL更改
for file in filelist:
    if file[-4] != '.':
        im = PIL.Image.open(path + file)
        im.save(savepath + file + '.png')  # or 'test.tif'
        #os.remove(os.path.join(path, file))
    else:
        a = file.split('.')
        filename = a[0]
        if a[-1] == 'jpg':
            im = PIL.Image.open(path+file)
            filename = os.path.splitext(file)[0]
            im.save(savepath+filename+'.png') # or 'test.tif'
            os.remove(os.path.join(path, file))
```

4. 视频加矩形框
```python
import cv2
 
# Create a VideoCapture object and read from input file
# If the input is the camera, pass 0 instead of the video file name
cap = cv2.VideoCapture('1.avi') #读取视频
 
# 判断视频是否读取成功
if (cap.isOpened()== False):
  print("Error opening video stream or file")
#获取帧
while(cap.isOpened()):
  # Capture frame-by-frame
  ret, frame = cap.read()
  if ret == True:
    # 在每一帧上画矩形，frame帧,(四个坐标参数),（颜色）,宽度
    cv2.rectangle(frame, (int(200), int(300)), (int(400), int(500)), (255, 255, 255), 4)
    # 显示视频
    cv2.imshow('Frame',frame)
    # 刷新视频
    cv2.waitKey(10)
 
    # 按q退出
    if cv2.waitKey(25) & 0xFF == ord('q'):
      break
 
  # Break the loop
  else:
    break

```

```
import numpy as np
import os
#加载3D关节点，第一个轴是帧号，第二个轴是关节点，第三个轴是坐标
'''
    "keypoints": {
        0: "nose",
        1: "left_eye",
        2: "right_eye",
        3: "left_ear",
        4: "right_ear",
        5: "left_shoulder",
        6: "right_shoulder",
        7: "left_elbow",
        8: "right_elbow",
        9: "left_wrist",
        10: "right_wrist",
        11: "left_hip",
        12: "right_hip",
        13: "left_knee",
        14: "right_knee",
        15: "left_ankle",
        16: "right_ankle"
    }
'''
#两脚距离：15 16  膝盖到脚距离：13 15

video = "hr_pose_2.mp4"
#joints_3d_path = 'input_3djoints/3d_2_world.npy'
basename = os.path.basename(video)
video_name = basename[:basename.rfind('.')]
result_video = 'dist_outputs/result_' + video_name

#加载npz文件
#print(coordinates_keypoints.files)
#coordinates_keypoints = np.load('bbac_demo.npz')

#加载npy文件
coordinates_keypoints = np.load('input_3djoints/3d_2_world.npy')
#coordinates_keypoints1 = np.load('2d_test_0304_normalize.npy')
#print(coordinates_keypoints[:,:,:])
#print(coordinates_keypoints[398,:,:])
#print(coordinates_keypoints.shape)

#print(dis_knee_ankle)
#print(dis_ankle_ankle)
#print(act_ankle_ankle)
#d = math.sqrt((x1-x2)**2+(y1-y2)**2+(z1-z2)**2)

import cv2
#读取视频
cap = cv2.VideoCapture(video)
#获取视频帧率
fps_video = cap.get(cv2.CAP_PROP_FPS)

#设置写入视频的编码格式
fourcc = cv2.VideoWriter_fourcc(*"mp4v")
#获取视频宽度
frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
#获取视频高度
frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
videoWriter = cv2.VideoWriter(result_video, fourcc, fps_video, (frame_width, frame_height))
frame_id = 0
while (cap.isOpened()):
    ret, frame = cap.read()
    if ret == True:
        frame_id += 1

        # 提取关节坐标并计算距离
        left_knee = coordinates_keypoints[frame_id - 1,13,:]
        left_ankle = coordinates_keypoints[frame_id - 1,15,:]
        right_ankle = coordinates_keypoints[frame_id - 1,16,:]

        dis_knee_ankle = np.sqrt(np.sum((left_knee - left_ankle)**2))
        dis_ankle_ankle = np.sqrt(np.sum((left_knee - right_ankle)**2))
        act_knee_ankle = 40
        act_ankle_ankle = (act_knee_ankle / dis_knee_ankle) * dis_ankle_ankle
        #act_ankle_ankle = 76 * dis_ankle_ankle

        # 文字坐标
        '''
        left_x_up = int(frame_width / frame_id)
        left_y_up = int(frame_height / frame_id)
        right_x_down = int(left_x_up + frame_width / 10)
        right_y_down = int(left_y_up + frame_height / 10)
        word_x = frame_width + 5
        word_y = frame_width + 25
        '''
        word_x = 5
        word_y = 55
        #各参数依次是：图片，添加的文字，左上角坐标，字体，字体大小，颜色，字体粗细
        cv2.putText(frame, 'dist = %s' %act_ankle_ankle, (word_x, word_y),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (55,255,155), 2)
        cv2.putText(frame, 'frane = %s' % frame_id, (word_x, word_y + 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (55, 255, 155),2)
        videoWriter.write(frame)

    else:
        videoWriter.release()
        break

```

6. 图片转视频

```python
import os
import cv2
import numpy as np

path = 'image/'

filelist = os.listdir(path)
for item in filelist:
    if item.startswith('.') and os.path.isfile(os.path.join(path, item)):
        filelist.remove(item)
print(filelist)
#os.listdir输出是乱序的，所以要对每个文件名将句号前的字符串转化为数字，然后以数字为key来进行排序
filelist.sort(key=lambda x:int(x[:-4]))

#当包含多种文件格式时
#filelist.sort(key=lambda x:int(x.split('.')[0]))


fps = 20  # 视频每秒20帧
size = (960, 540)  # 需要转为视频的图片的尺寸
# 可以使用cv2.resize()进行修改

video = cv2.VideoWriter("test_0304.avi", cv2.VideoWriter_fourcc('I', '4', '2', '0'), fps, size)
# 视频保存在当前目录下

for item in filelist:
    if item.endswith('.jpg'):
# 找到路径中所有后缀名为.png的文件，可以更换为.jpg或其它
        item = path + item
        img = cv2.imread(item)
        video.write(img)

video.release()


'''
#修改尺寸
for i in range(832,1075):
    read_path = path + '%s'%i + '.jpg'
    src = cv2.imread(read_path)

    j = i - 799
    save_path = path  + '%s'%j  + '.jpg'
    cv2.imwrite(save_path, src)

import os
from PIL import Image

filename = os.listdir("/Users/dushuai/Desktop/tools/picture/")
base_dir = "/Users/dushuai/Desktop/tools/picture/"
new_dir = "/Users/dushuai/Desktop/tools/picture1/"
size_m = 640
size_n = 480

for img in filename:
    image = Image.open(base_dir + img)
    image_size = image.resize((size_m, size_n), Image.ANTIALIAS)
    image_size.save(new_dir + img)
'''
```
7. 视频转图片
```
import cv2
def getFrame(videoPath, svPath):
    cap = cv2.VideoCapture(videoPath)
    numFrame = 0
    while True:
        if cap.grab():
            flag, frame = cap.retrieve()
            if not flag:
                continue
            else:
                #cv2.imshow('video', frame)
                numFrame += 1
                print(numFrame)
                newPath = svPath + str(numFrame) + ".jpg"
                cv2.imencode('.jpg', frame)[1].tofile(newPath)

        if cv2.waitKey(10) == 27:
            break

getFrame('hr_pose_bbac_demo.mp4','output/')
```