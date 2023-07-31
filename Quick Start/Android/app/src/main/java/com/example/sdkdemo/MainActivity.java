package com.example.sdkdemo;

import android.os.Bundle;

import com.example.sdkdemo.base.BaseListActivity;
import com.example.sdkdemo.feature.MultiMediaStreamActivity;
import com.example.sdkdemo.feature.RotationModeActivity;
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
        holder.addItem(R.string.file_exchange, R.string.file_exchange_desc, FeatureActivity.class, Feature.FEATURE_FILE_EXCHANGE);
        holder.addItem(R.string.location, R.string.location_desc, FeatureActivity.class, Feature.FEATURE_LOCATION);
        holder.addItem(R.string.pod_control, R.string.pod_control_desc, FeatureActivity.class, Feature.FEATURE_POD_CONTROL);
        holder.addItem(R.string.rotation_mode, R.string.rotation_mode_desc, RotationModeActivity.class, Feature.FEATURE_ROTATION_MODE);
        holder.addItem(R.string.multi_media_stream, R.string.multi_media_stream_desc, MultiMediaStreamActivity.class, Feature.FEATURE_MULTI_MEDIA_STREAM);
    }

    @Override
    public int titleRes() {
        return R.string.app_name;
    }
}
