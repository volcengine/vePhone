package com.example.sdkdemo;

import android.os.Bundle;

import com.example.sdkdemo.base.BaseListActivity;
import com.example.sdkdemo.feature.AppGroundSwitchManagerActivity;
import com.example.sdkdemo.feature.AudioServiceActivity;
import com.example.sdkdemo.feature.CameraManagerActivity;
import com.example.sdkdemo.feature.ClarityServiceActivity;
import com.example.sdkdemo.feature.ClipBoardServiceManagerActivity;
import com.example.sdkdemo.feature.FileExchangeActivity;
import com.example.sdkdemo.feature.GamePadServiceActivity;
import com.example.sdkdemo.feature.LocalInputManagerActivity;
import com.example.sdkdemo.feature.LocationServiceActivity;
import com.example.sdkdemo.feature.MessageChannelActivity;
import com.example.sdkdemo.feature.MultiMediaStreamActivity;
import com.example.sdkdemo.feature.OthersActivity;
import com.example.sdkdemo.feature.PodControlServiceActivity;
import com.example.sdkdemo.feature.RotationModeActivity;
import com.example.sdkdemo.feature.SensorActivity;
import com.example.sdkdemo.feature.TouchEventServiceActivity;
import com.example.sdkdemo.feature.VideoRenderModeManagerActivity;

public class MainActivity extends BaseListActivity {

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
    }

    @Override
    protected void setupAdapter(ItemsHolder holder) {
        holder.addItem(R.string.audio, R.string.audio_desc, AudioServiceActivity.class);
        holder.addItem(R.string.camera, R.string.camera_desc, CameraManagerActivity.class);
        holder.addItem(R.string.clarity, R.string.clarity_desc, ClarityServiceActivity.class);
        holder.addItem(R.string.clipboard, R.string.clipboard_desc, ClipBoardServiceManagerActivity.class);
        holder.addItem(R.string.file_exchange, R.string.file_exchange_desc, FileExchangeActivity.class);
        holder.addItem(R.string.game_pad, R.string.game_pad_desc, GamePadServiceActivity.class);
        holder.addItem(R.string.local_input, R.string.local_input_desc, LocalInputManagerActivity.class);
        holder.addItem(R.string.location, R.string.location_desc, LocationServiceActivity.class);
        holder.addItem(R.string.message_channel, R.string.message_channel_desc, MessageChannelActivity.class);
        holder.addItem(R.string.pod_control, R.string.pod_control_desc, PodControlServiceActivity.class);
        holder.addItem(R.string.remote_app_ground_switch, R.string.remote_app_ground_switch_desc, AppGroundSwitchManagerActivity.class);
        holder.addItem(R.string.rotation_mode, R.string.rotation_mode_desc, RotationModeActivity.class);
        holder.addItem(R.string.touch_event, R.string.touch_event_desc, TouchEventServiceActivity.class);
        holder.addItem(R.string.multi_media_stream, R.string.multi_media_stream_desc, MultiMediaStreamActivity.class);
        holder.addItem(R.string.video_render_mode, R.string.video_render_mode_desc, VideoRenderModeManagerActivity.class);
        holder.addItem(R.string.sensor, R.string.sensor_desc, SensorActivity.class);
        holder.addItem(R.string.unclassified, R.string.unclassified_desc, OthersActivity.class);
    }

    @Override
    public int titleRes() {
        return R.string.app_name;
    }
}
