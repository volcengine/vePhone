package com.example.sdkdemo.base;

import static android.content.pm.ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE;
import static android.content.pm.ActivityInfo.SCREEN_ORIENTATION_SENSOR_PORTRAIT;

import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;

import com.example.sdkdemo.R;

public class BasePlayActivity extends AppCompatActivity  {

    private long lastBackPress;

    /**
     * 调整Activity的显示方向
     *
     * @param rotation 旋转方向
     *                 0/180  -- 将Activity调整为竖屏显示
     *                 90/270 -- 将Activity调整为横屏显示
     */
    protected void setRotation(int rotation) {
        switch (rotation) {
            case 0:
            case 180:
                setRequestedOrientation(SCREEN_ORIENTATION_SENSOR_PORTRAIT);
                break;
            case 90:
            case 270:
                setRequestedOrientation(SCREEN_ORIENTATION_SENSOR_LANDSCAPE);
                break;
        }
    }

    @Override
    public void onBackPressed() {
        long current = System.currentTimeMillis();
        if (current - lastBackPress < 1000L) {
            super.onBackPressed();
        } else {
            Toast.makeText(this, getString(R.string.back_again_to_exit), Toast.LENGTH_SHORT).show();
            lastBackPress = current;
        }
    }

    protected void showToast(String s) {
        Toast.makeText(this, s, Toast.LENGTH_SHORT).show();
    }

}
