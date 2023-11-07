package com.example.sdkdemo.feature;

import android.content.Context;
import android.view.View;
import android.widget.Button;
import android.widget.ScrollView;
import android.widget.Toast;

import androidx.appcompat.widget.SwitchCompat;

import com.example.sdkdemo.R;
import com.example.sdkdemo.util.DialogUtils;
import com.volcengine.phone.VePhoneEngine;

public class SensorView {

    private DialogUtils.DialogWrapper mDialogWrapper;

    public SensorView(Context context, Button button) {
        mDialogWrapper = DialogUtils.wrapper(new TestView(context));
        button.setVisibility(View.VISIBLE);
        button.setOnClickListener(v -> mDialogWrapper.show());
    }

    private static class TestView extends ScrollView {
        public TestView(Context context) {
            super(context);
            inflate(context, R.layout.dialog_sensor, this);

            SwitchCompat switchCompatAccelSensor = findViewById(R.id.switch_enable_accelerator);
            switchCompatAccelSensor.setOnCheckedChangeListener((buttonView, isChecked) -> {
                /**
                 * enableAccelSensor(boolean enable) -- 本地加速度传感器开关
                 */
                VePhoneEngine.getInstance().enableAccelSensor(isChecked);
                Toast.makeText(context, "本地加速度传感器" + (isChecked ? "已开启" : "已关闭"), Toast.LENGTH_SHORT).show();
            });

            SwitchCompat switchCompatMagnetic = findViewById(R.id.switch_enable_magnetic);
            switchCompatMagnetic.setOnCheckedChangeListener((buttonView, isChecked) -> {
                /**
                 * enableMagneticSensor(boolean enable) -- 本地磁力传感器开关
                 */
                VePhoneEngine.getInstance().enableMagneticSensor(isChecked);
                Toast.makeText(context, "本地磁力传感器" + (isChecked ? "已开启" : "已关闭"), Toast.LENGTH_SHORT).show();
            });

            SwitchCompat switchCompatGravity = findViewById(R.id.switch_enable_gravity);
            switchCompatGravity.setOnCheckedChangeListener((buttonView, isChecked) -> {
                /**
                 * enableGravitySensor(boolean enable) -- 本地重力传感器开关
                 */
                VePhoneEngine.getInstance().enableGravitySensor(isChecked);
                Toast.makeText(context, "本地重力传感器" + (isChecked ? "已开启" : "已关闭"), Toast.LENGTH_SHORT).show();
            });

            SwitchCompat switchCompatOrientation = findViewById(R.id.switch_enable_orientation);
            switchCompatOrientation.setOnCheckedChangeListener((buttonView, isChecked) -> {
                /**
                 * enableOrientationSensor(boolean enable) -- 本地方向传感器开关
                 */
                VePhoneEngine.getInstance().enableOrientationSensor(isChecked);
                Toast.makeText(context, "本地方向传感器" + (isChecked ? "已开启" : "已关闭"), Toast.LENGTH_SHORT).show();
            });

            SwitchCompat switchCompatGyroscope = findViewById(R.id.switch_enable_gyroscope);
            switchCompatGyroscope.setOnCheckedChangeListener((buttonView, isChecked) -> {
                /**
                 * enableGyroscopeSensor(boolean enable) -- 本地陀螺仪传感器开关
                 */
                VePhoneEngine.getInstance().enableGyroscopeSensor(isChecked);
                Toast.makeText(context, "本地陀螺仪传感器" + (isChecked ? "已开启" : "已关闭"), Toast.LENGTH_SHORT).show();
            });

            SwitchCompat switchCompatVibrator = findViewById(R.id.switch_enable_vibrator);
            switchCompatVibrator.setOnCheckedChangeListener((buttonView, isChecked) -> {
                /**
                 * enableVibrator(boolean enable) -- 本地振动传感器开关
                 */
                VePhoneEngine.getInstance().enableVibrator(isChecked);
                Toast.makeText(context, "本地振动传感器" + (isChecked ? "已开启" : "已关闭"), Toast.LENGTH_SHORT).show();
            });
        }
    }


}
