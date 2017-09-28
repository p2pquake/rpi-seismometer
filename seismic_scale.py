
import time
import datetime
import math
import socket

import spidev
import os
import sys

# FPS制御 -----
# ターゲットFPS
target_fps = 200

start_time = time.time()
frame = 0

# SPIセンサ制御 -----
spi = spidev.SpiDev()
spi.open(0,0)
spi.max_speed_hz = 1000*1000

def ReadChannel(channel):
    adc = spi.xfer2([(0x07 if (channel & 0x04) else 0x06), (channel & 0x03) << 6, 0])
    data = ((adc[1] & 0x0f) << 8 ) | adc[2]
    return data

# 加速度データ制御 -----
# A/Dコンバータ値 -> ガル値 係数
ad2gal = 1.13426
# 0.3秒空間数
a_frame  = int(target_fps * 0.3)

# 地震データ -----
adc_values = [[1] * target_fps, [1] * target_fps, [1] * target_fps]
rc_values   = [0, 0, 0]
a_values = [0] * target_fps * 5

a_ring_index = 0

# リアルタイム震度計算 -----
while True:
    # リングバッファ位置計算
    a_ring_index = (a_ring_index + 1) % (target_fps * 5)

    # 3軸サンプリング
    for i in range(3):
        val = ReadChannel(i)
        adc_values[i].append(val)
        adc_values[i].pop(0)
   
    # フィルタ適用及び加速度変換
    axis_gals = [0, 0, 0]
    for i in range(3):
        offset = sum(adc_values[i])/len(adc_values[i])
        rc_values[i] = rc_values[i]*0.94+adc_values[i][target_fps-1]*0.06
        axis_gals[i] = (rc_values[i] - offset) * ad2gal

    # 3軸合成加速度算出
    composite_gal = math.sqrt(axis_gals[0]**2 + axis_gals[1]**2 + axis_gals[2]**2)

    # 加速度リングバッファに格納
    a_values[a_ring_index] = composite_gal

    # 0.3秒以上継続した合成加速度から震度を算出
    seismic_scale = 0
    min_a = sorted(a_values)[-a_frame]
    if min_a > 0:
      seismic_scale = 2 * math.log10(min_a) + 0.94

    # 0.1秒おきに出力
    if frame % (target_fps / 10) == 0:
        print(datetime.datetime.now(), "scale:" , seismic_scale, " frame:", frame)

    # 次フレームの開始時間を計算
    frame += 1
    next_frame_time = frame / target_fps

    # 残時間を計算し、スリープ
    current_time = time.time()
    remain_time = next_frame_time - (current_time - start_time)

    if remain_time > 0:
        time.sleep(remain_time)

    # フレーム数は32bit long値の上限あたりでリセットしておく
    if frame >= 2147483647:
        start_time = current_time
        frame = 1

