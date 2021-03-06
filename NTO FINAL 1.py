# UnderWaterDogs
import math
import time

import cv2 as cv
import cv2.aruco
import numpy as np
import pymurapi as mur

auv = mur.mur_init()
degree, angle = 0, 0
colors = {'magenta': ((133, 0, 0), (180, 255, 255)),
          'yellow': ((10, 220, 50), (30, 255, 255)),
          'green': ((60, 0, 0), (91, 255, 255)),
          'blue': ((130, 166, 0), (135, 255, 255)),
          'code': ((0, 0, 0), (60, 40, 40))}
way, way_col, nowPoint = '', [], 0
x_center, y_center, x, y = 999, 999, 999, 999


def clamp(v, min, max):
    if v > max:
        return max
    if v < min:
        return min
    return v


class PD(object):
    _kp = 0.0
    _kd = 0.0
    _prev_error = 0.0
    _timestamp = 0

    def __init__(self):
        pass

    def set_p(self, value):
        self._kp = value

    def set_d(self, value):
        self._kd = value

    def process(self, error):
        timestamp = int(round(time.time() * 1000))
        out = self._kp * error + self._kd / (timestamp - self._timestamp) * (error - self._prev_error)
        self._timestamp = timestamp
        self._prev_error = error
        return out


def keep_depth(depth, P, D):
    try:
        error = auv.get_depth() - depth
        out = keep_depth.reg.process(error)
        out = clamp(out, -100, 100)
        auv.set_motor_power(2, out)
        auv.set_motor_power(3, out)
    except:
        keep_depth.reg = PD()
        keep_depth.reg.set_p(P)
        keep_depth.reg.set_d(D)


def to_180(angle):
    if angle > 180.0:
        return angle - 360
    if angle < -180.0:
        return angle + 360
    return angle


def keep_yaw(yaw, power, P, D):
    to_180(yaw)
    try:
        error = auv.get_yaw() - yaw
        error = to_180(error)
        out = keep_yaw.reg.process(error)
        out = clamp(out, -100, 100)
        auv.set_motor_power(0, clamp((power - out), -100, 100))
        auv.set_motor_power(1, clamp((power + out), -100, 100))
    except:
        keep_yaw.reg = PD()
        keep_yaw.reg.set_p(P)
        keep_yaw.reg.set_d(D)


def get_cont(img, color):
    img_hsv = cv.cvtColor(img, cv.COLOR_BGR2HSV)
    mask = cv.inRange(img_hsv, color[0], color[1])
    contours, _ = cv.findContours(mask, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE)
    return contours


def draw_cont(img, contour):
    global x_center, y_center, x, y
    if cv.contourArea(contour) < 100:
        return
    cv.drawContours(img, [contour], 0, (0, 0, 0), 2)
    moments = cv.moments(contour)
    xm1 = moments['m10']
    xm2 = moments['m00']
    ym1 = moments['m01']
    ym2 = moments['m00']
    x = int(xm1 / xm2)
    y = int(ym1 / ym2)
    x_center = x - (320 / 2)
    y_center = y - (240 / 2)
    cv.circle(img, (x, y), 3, (0, 0, 255), -1)

def get_color(color):
    img = auv.get_image_bottom()
    cont_img = img.copy()
    for _ in colors:
        contours = get_cont(img, colors[color])
        if not contours:
            continue
        for cnt in contours:
            draw_cont(cont_img, cnt)
    cv.imshow("gen", img)
    cv.imshow("cont", cont_img)
    cv.waitKey(1)
    return contours, img


def turn(degres, depth, time_):
    timing = time.time()
    while True:
        get_color('green')
        keep_depth(depth, 70, 5)
        keep_yaw(degres, 0, 0.8, 0.5)
        if time.time() - timing > time_:
            timing = time.time()
            break


def go(degres, power, time_, depth, color):
    global angle
    timing = time.time()
    while True:
        cnt = get_color(color)
        keep_depth(depth, 50, 7)
        keep_yaw(degres, power, 0.8, 0.5)
        if time.time() - timing > time_:
            if cnt is not None:
                try:
                    angle = (angle + 180 + 180) % 360 - 180
                except:
                    pass
            timing = time.time()
            break


def depthing(depth, time_):
    timing = time.time()
    while True:
        get_color('green')
        keep_depth(depth, 20, 2.5)
        if time.time() - timing > time_:
            timing = time.time()
            break


def centralize(color, depth):
    x_center = x - (320 / 2)
    y_center = y - (240 / 2) + 22
    keep_depth(depth, 20, 1)
    try:
        get_color(color)
        lenght = math.sqrt(x_center ** 2 + y_center ** 2)
        if lenght < 7.0:
            auv.set_motor_power(0, 0)
            auv.set_motor_power(1, 0)
            auv.set_motor_power(4, 0)
            return True
        outForward = centralize.regForward.process(y_center)
        outForward = clamp(outForward, -10, 10)
        outSide = centralize.regSide.process(x_center)
        outSide = clamp(outSide, -10, 10)
        auv.set_motor_power(0, -outForward)
        auv.set_motor_power(1, -outForward)
        auv.set_motor_power(4, -outSide)
    except:
        centralize.regForward = PD()
        centralize.regForward.set_p(0.15)
        centralize.regForward.set_d(0.1)

        centralize.regSide = PD()
        centralize.regSide.set_p(0.1)
        centralize.regSide.set_d(0.15)
    return False


def area_shape(color, img):
    contours = get_cont(img, colors[color])
    if contours:
        for cnt in contours:
            area = cv.contourArea(cnt)
            if area < 500:
                continue
            (circle_x, circle_y), circle_radius = cv.minEnclosingCircle(cnt)
            circle_area = circle_radius ** 2 * math.pi - 0.5
            rectangle = cv.minAreaRect(cnt)
            box = cv.boxPoints(rectangle)
            box = np.int0(box)
            rectangle_area = cv.contourArea(box)
            rect_w, rect_h = rectangle[1][0], rectangle[1][1]
            aspect_ratio = max(rect_w, rect_h) / min(rect_w, rect_h)
            try:
                triangle = cv.minEnclosingTriangle(cnt)[1]
                triangle = np.int0(triangle)
                triangle_area = cv.contourArea(triangle)
            except:
                triangle_area = 0
            shapes_areas = {
                'circle': circle_area,
                'rectangle' if aspect_ratio > 1.5 else 'square': rectangle_area,
                'triangle': triangle_area,
            }
            diffs = {
                name: abs(area - shapes_areas[name]) for name in shapes_areas
            }
            shape_name = min(diffs, key=diffs.get)
            return shape_name


def calc_angle(color, imge):
    cnt = get_cont(imge, colors[color])
    if cnt:
        for contour in cnt:
            rectangle = cv.minAreaRect(contour)
            box = cv.boxPoints(rectangle)
            box = np.int0(box)
            edge_first = np.int0((box[1][0] - box[0][0], box[1][1] - box[0][1]))
            edge_second = np.int0((box[2][0] - box[1][0], box[2][1] - box[1][1]))
            edge = edge_first
            if cv.norm(edge_second) > cv.norm(edge_first):
                edge = edge_second
            angle = -((180.0 / math.pi * math.acos(edge[0] / (cv.norm((1, 0)) * cv.norm(edge)))) - 90)
        return angle


def turn_to_fig(color):
    _, imge = get_color(color)
    power = calc_angle(color, imge)
    shape = area_shape(color, imge)
    if shape != 'circle':
        try:
            auv.set_motor_power(1, -power)
            auv.set_motor_power(0, power)
        except:
            pass
    centralize(color, 3.1)
    keep_depth(2.5, 30, 2)
    return power


def wayF():
    for i in range(3):
        if way[i + 2] == '1':
            way_col.append('green')
        elif way[i + 2] == '2':
            way_col.append('yellow')
        else:
            way_col.append('magenta')


st_ang = auv.get_yaw()
# --------------scan aruco------------#
while True:
    keep_depth(2.2, 20, 1)
    img = auv.get_image_bottom()
    arucoDict = cv.aruco.Dictionary_get(cv.aruco.DICT_4X4_1000)
    arucoParams = cv.aruco.DetectorParameters_create()
    (corners, ids, rejected) = cv.aruco.detectMarkers(img, arucoDict,
                                                       parameters=arucoParams)
    way = ids
    way = str(way)
    if ids is not None:
        break
# ---------------grabbing-------------#
wayF()
print(way_col)
for i in range(3):
    cn = 0
    cc = 0
    while True:
        _, imge = get_color(way_col[nowPoint])
        keep_depth(1.8, 20, 1)
        keep_yaw(st_ang, 0, 1, 1)
        if st_ang - 5 < auv.get_yaw() < st_ang + 5:
            cc += 1
            if cc >= 15:
                break
        else:
            cc = 0
    cc = 0
    if y_center > 100:
        while True:
            _, imge = get_color(way_col[nowPoint])
            keep_depth(1.8, 20, 1)
            st_ange = to_180(st_ang+180)
            keep_yaw(st_ange, 0, 1, 1)
            if st_ange - 5 < auv.get_yaw() < st_ange + 5:
                cc += 1
                if cc >= 15:
                    go(st_ang+180, 20, 1, 1.8, way_col[nowPoint])
                    break
            else:
                cc = 0
    error = 1
    while True:
        try:
            if y_center > 100:
                while True:
                    _, imge = get_color(way_col[nowPoint])
                    keep_depth(1.8, 20, 1)
                    st_ange = to_180(st_ang + 180)
                    keep_yaw(st_ange, 0, 1, 1)
                    if st_ange - 5 < auv.get_yaw() < st_ange + 5:
                        cc += 1
                        if cc >= 15:
                            go(st_ang + 180, 20, 1, 1.8, way_col[nowPoint])
                            break
                    else:
                        cc = 0
            if -1 < error < 1:
                cn += 1
                if cn >= 16 and y_center < 100:
                    angle = auv.get_yaw()
                    auv.set_motor_power(1, 0)
                    auv.set_motor_power(2, 0)
                    break
            else:
                cn = 0
            error = turn_to_fig(way_col[nowPoint])
        except:
            pass
    while True:
        keep_depth(2.4, 50, 1)
        keep_yaw(angle, 80, 1, 1)
        _, img = get_color(way_col[nowPoint])
        shape = area_shape(way_col[nowPoint], img)
        if shape == 'circle':
            auv.set_motor_power(0, 0)
            auv.set_motor_power(1, 0)
            break
    while True:
        s = centralize(way_col[nowPoint], 3.11)
        get_color(way_col[nowPoint])
        if way_col[nowPoint] != 'magenta':
            keep_depth(3.1, 20, 1)
        else:
            keep_depth(2.7, 20, 1)
        keep_yaw(angle, 0, 1, 1)
        if s:
            break
    while True:
        img = auv.get_image_bottom()
        shape = area_shape('blue', img)
        if way_col[nowPoint] != 'magenta':
            cnt = get_color('blue')
            if centralize('blue', 3.3):
                break
        else:
            cnt = get_color('blue')
            if centralize('blue', 3.3) and shape == 'circle':
                break
            elif centralize('blue', 3.3) and shape != 'circle':
                gr_ang = auv.get_yaw()
                go(gr_ang, -30, 1, 3.3, 'blue')
    auv.open_grabber()
    if way_col[nowPoint] == 'magenta':
        try:
            go(gr_ang, -10, 0.5, 3.3, 'blue')
        except:
            pass
    auv.set_motor_power(0, 0)
    auv.set_motor_power(1, 0)
    auv.set_motor_power(4, 0)
    depthing(3.8, 8)
    auv.close_grabber()
    time.sleep(1)
    angle = angle+180
    angle_c = to_180(angle)
    cc = 0
    while True:
        get_color(way_col[nowPoint])
        keep_yaw(angle, 0, 1, 1)
        keep_depth(2.7, 20, 1)
        if angle_c - 5 < auv.get_yaw() < angle_c + 5:
            cc += 1
            if cc >= 15:
                break
        else:
            cc = 0
    go(angle, 20, 4, 2.7, way_col[nowPoint])
    angle = auv.get_yaw()
    while True:
        keep_depth(2.7, 50, 1)
        keep_yaw(angle, 80, 1, 1)
        _, img = get_color('code')
        shape = area_shape('code', img)
        if shape == 'rectangle' or shape == 'triangle':
            go(angle, -100, 1, 2.7, 'code')
            keep_yaw(angle, 0, 1, 1)
            break
    while True:
        auv.open_grabber()
        get_color('code')
        keep_depth(1.5, 20, 1)
        if centralize('code', 1.6):
            break
    nowPoint += 1
while True:
    keep_depth(0, 20, 1)
