package com.example.sdkdemo;

import android.os.Bundle;

import com.example.sdkdemo.base.BaseListActivity;
import com.example.sdkdemo.feature.ClarityServiceActivity;
import com.example.sdkdemo.feature.ClipBoardServiceManagerActivity;
import com.example.sdkdemo.feature.MessageChannelActivity;
import com.example.sdkdemo.feature.MultiMediaStreamActivity;
import com.example.sdkdemo.feature.OthersActivity;
import com.example.sdkdemo.feature.PodControlServiceActivity;
import com.example.sdkdemo.feature.RotationModeActivity;
import com.example.sdkdemo.feature.SensorActivity;
import com.example.sdkdemo.util.Feature;

public class MainActivity extends BaseListActivity {

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
    }

    @Override
    protected void setupAdapter(ItemsHolder holder) {
        holder.addItem(R.string.audio, R.string.audio_desc, FeatureActivity.class, Feature.FEATURE_AUDIO);
        holder.addItem(R.string.camera, R.string.camera_desc, FeatureActivity.class, Feature.FEATURE_CAMERA);
        holder.addItem(R.string.clarity, R.string.clarity_desc, ClarityServiceActivity.class, -1);
        holder.addItem(R.string.clipboard, R.string.clipboard_desc, ClipBoardServiceManagerActivity.class, -1);
        holder.addItem(R.string.file_exchange, R.string.file_exchange_desc, FeatureActivity.class, Feature.FEATURE_FILE_EXCHANGE);
        holder.addItem(R.string.location, R.string.location_desc, FeatureActivity.class, Feature.FEATURE_LOCATION);
        holder.addItem(R.string.message_channel, R.string.message_channel_desc, MessageChannelActivity.class, -1);
        holder.addItem(R.string.pod_control, R.string.pod_control_desc, PodControlServiceActivity.class, -1);
        holder.addItem(R.string.rotation_mode, R.string.rotation_mode_desc, RotationModeActivity.class, Feature.FEATURE_ROTATION_MODE);
        holder.addItem(R.string.multi_media_stream, R.string.multi_media_stream_desc, MultiMediaStreamActivity.class, Feature.FEATURE_MULTI_MEDIA_STREAM);
        holder.addItem(R.string.sensor, R.string.sensor_desc, SensorActivity.class, -1);
        holder.addItem(R.string.unclassified, R.string.unclassified_desc, OthersActivity.class, -1);
    }

    @Override
    public int titleRes() {
        return R.string.app_name;
    }
}
