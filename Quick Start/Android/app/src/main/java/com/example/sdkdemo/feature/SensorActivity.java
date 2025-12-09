package com.example.sdkdemo.feature;

import android.os.Bundle;
import android.util.Log;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.appcompat.widget.LinearLayoutCompat;
import androidx.appcompat.widget.SwitchCompat;

import com.example.sdkdemo.R;
import com.example.sdkdemo.util.ScreenUtil;
import com.example.sdkdemo.base.BasePlayActivity;
import com.example.sdkdemo.util.SdkUtil;
import com.volcengine.cloudphone.apiservice.SensorService;
import com.volcengine.phone.PhonePlayConfig;
import com.volcengine.phone.VePhoneEngine;

import java.util.Map;

/**
 * 该类用于展示与本地传感器相关的功能接口
 *
 * 是否开启传感器有两种方式，
 * 一种是通过{@link com.volcengine.phone.PhonePlayConfig.Builder}来设置，
 * 具体示例代码见{@link SensorActivity#initPlayConfigAndStartPlay()}；
 * 另一种是通过{@link VePhoneEngine#enableAccelSensor(boolean)}等接口来设置，
 * 具体示例代码见{@link SensorActivity#initView()}。
 */
public class SensorActivity extends BasePlayActivity {

    private ViewGroup mContainer;
    private SwitchCompat mSwShowOrHide, mSwEnableMagnetic, mSwEnableAccelerator,
            mSwEnableGravity, mSwEnableOrientation, mSwEnableGyroscope, mSwEnableVibrator;
    private LinearLayoutCompat mLlButtons;

    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        ScreenUtil.adaptHolePhone(this);
        setContentView(R.layout.activity_sensor);
        initView();
        initPlayConfigAndStartPlay();
    }

    private void initView() {
        mContainer = findViewById(R.id.container);
        mSwShowOrHide = findViewById(R.id.sw_show_or_hide);
        mLlButtons = findViewById(R.id.ll_buttons);
        mSwEnableMagnetic = findViewById(R.id.sw_enable_magnetic);
        mSwEnableAccelerator = findViewById(R.id.sw_enable_accelerator);
        mSwEnableGravity = findViewById(R.id.sw_enable_gravity);
        mSwEnableOrientation = findViewById(R.id.sw_enable_orientation);
        mSwEnableGyroscope = findViewById(R.id.sw_enable_gyroscope);
        mSwEnableVibrator = findViewById(R.id.sw_enable_vibrator);

        mSwShowOrHide.setOnCheckedChangeListener((buttonView, isChecked) -> {
            mLlButtons.setVisibility(isChecked ? View.VISIBLE : View.GONE);
        });

        mSwEnableMagnetic.setOnCheckedChangeListener((buttonView, isChecked) -> {
            /**
             * enableMagneticSensor(boolean enable) -- 本地磁力传感器开关
             */
            VePhoneEngine.getInstance().enableMagneticSensor(isChecked);
            Toast.makeText(SensorActivity.this, "本地磁力传感器" + (isChecked ? "已开启" : "已关闭"), Toast.LENGTH_SHORT).show();
        });

        mSwEnableAccelerator.setOnCheckedChangeListener((buttonView, isChecked) -> {
            /**
             * enableAccelSensor(boolean enable) -- 本地加速度传感器开关
             */
            VePhoneEngine.getInstance().enableAccelSensor(isChecked);
            Toast.makeText(SensorActivity.this, "本地加速度传感器" + (isChecked ? "已开启" : "已关闭"), Toast.LENGTH_SHORT).show();
        });

        mSwEnableGravity.setOnCheckedChangeListener((buttonView, isChecked) -> {
            /**
             * enableGravitySensor(boolean enable) -- 本地重力传感器开关
             */
            VePhoneEngine.getInstance().enableGravitySensor(isChecked);
            Toast.makeText(SensorActivity.this, "本地重力传感器" + (isChecked ? "已开启" : "已关闭"), Toast.LENGTH_SHORT).show();
        });

        mSwEnableOrientation.setOnCheckedChangeListener((buttonView, isChecked) -> {
            /**
             * enableOrientationSensor(boolean enable) -- 本地方向传感器开关
             */
            VePhoneEngine.getInstance().enableOrientationSensor(isChecked);
            Toast.makeText(SensorActivity.this, "本地方向传感器" + (isChecked ? "已开启" : "已关闭"), Toast.LENGTH_SHORT).show();
        });

        mSwEnableGyroscope.setOnCheckedChangeListener((buttonView, isChecked) -> {
            /**
             * enableGyroscopeSensor(boolean enable) -- 本地陀螺仪传感器开关
             */
            VePhoneEngine.getInstance().enableGyroscopeSensor(isChecked);
            Toast.makeText(SensorActivity.this, "本地陀螺仪传感器" + (isChecked ? "已开启" : "已关闭"), Toast.LENGTH_SHORT).show();
        });

        mSwEnableVibrator.setOnCheckedChangeListener((buttonView, isChecked) -> {
            /**
             * enableVibrator(boolean enable) -- 本地振动传感器开关
             */
            VePhoneEngine.getInstance().enableVibrator(isChecked);
            Toast.makeText(SensorActivity.this, "本地振动传感器" + (isChecked ? "已开启" : "已关闭"), Toast.LENGTH_SHORT).show();
        });
    }

    private void initPlayConfigAndStartPlay() {
        SdkUtil.PlayAuth auth = SdkUtil.getPlayAuth(this);
        String roundId = "roundId_123";
        PhonePlayConfig.Builder builder = new PhonePlayConfig.Builder();
        builder.userId(SdkUtil.getClientUid())
                .ak(auth.ak)
                .sk(auth.sk)
                .token(auth.token)
                .container(mContainer)
                .enableLocalKeyboard(true)
                .roundId(roundId)
                .podId(auth.podId)
                .productId(auth.productId)
                .streamListener(this);
        VePhoneEngine.getInstance().start(builder.build(), this);
    }

    @Override
    protected void onResume() {
        super.onResume();
        VePhoneEngine.getInstance().resume();
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
    }

    @Override
    protected void onPause() {
        super.onPause();
        VePhoneEngine.getInstance().pause();
        getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
    }

    @Override
    public void finish() {
        VePhoneEngine.getInstance().stop();
        super.finish();
    }

    /**
     * 加入房间前回调，用于获取并初始化各个功能服务，例如设置各种事件监听回调。
     */
    @Override
    public void onServiceInit(@NonNull Map<String, Object> extras) {
        super.onServiceInit(extras);
        SensorService service = VePhoneEngine.getInstance().getSensorService();
        if (service != null) {
            service.setSensorsStateListener(new SensorService.SensorsStateListener() {
                /**
                 * 传感器开关状态改变的回调
                 *
                 * @param callUserId 改变传感器开关状态的用户ID
                 * @param type 传感器类型
                 *             1 -- TYPE_ACCELERATION
                 *             2 -- TYPE_GYROSCOPE
                 *             3 -- TYPE_MAGNETIC
                 *             4 -- TYPE_ORIENTATION
                 *             5 -- TYPE_GRAVITY
                 *             20 -- TYPE_LOCATION
                 * @param state 传感器开关状态 true：开启 false：关闭
                 * @param code 错误码 0：成功 <0：失败
                 * @param msg 错误信息
                 */
                @Override
                public void onSensorsStateChanged(String callUserId, int type, boolean state, int code, String msg) {
                    Log.d(TAG, "onSensorsStateChanged: callUserId:" + callUserId + ", type:" + type + ", state:" + state + ", code:" + code + ", msg:" + msg);
                }

                /**
                 * 获取传感器开关状态的结果回调
                 *
                 * @param type 传感器类型
                 *             1 -- TYPE_ACCELERATION
                 *             2 -- TYPE_GYROSCOPE
                 *             3 -- TYPE_MAGNETIC
                 *             4 -- TYPE_ORIENTATION
                 *             5 -- TYPE_GRAVITY
                 *             20 -- TYPE_LOCATION
                 * @param state 传感器开关状态 true：开启 false：关闭
                 * @param code 错误码 0：成功 <0：失败
                 * @param msg 错误信息
                 */
                @Override
                public void onGetSensorsState(int type, boolean state, int code, String msg) {
                    Log.d(TAG, "onGetSensorsState: type:" + type + ", state:" + state + ", code:" + code + ", msg:" + msg);
                }
            });
        }
    }

}
