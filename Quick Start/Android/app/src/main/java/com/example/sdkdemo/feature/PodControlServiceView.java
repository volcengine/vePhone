package com.example.sdkdemo.feature;

import android.content.Context;
import android.text.TextUtils;
import android.util.Log;
import android.view.View;
import android.widget.Button;
import android.widget.CompoundButton;
import android.widget.EditText;
import android.widget.ImageView;
import android.widget.ScrollView;
import android.widget.Switch;
import android.widget.TextView;

import androidx.appcompat.widget.SwitchCompat;
import androidx.core.util.Consumer;

import com.blankj.utilcode.util.ToastUtils;
import com.example.sdkdemo.R;
import com.example.sdkdemo.util.DialogUtils;
import com.volcengine.cloudphone.apiservice.PodControlService;

import java.text.DateFormat;
import java.text.MessageFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.List;

public class PodControlServiceView {

    private final PodControlService mPodControlService;
    private static final String TAG = "PodControlServiceView";
    private DialogUtils.DialogWrapper mDialogWrapper;
    private TestView mTestView;

    public PodControlServiceView(Context context, PodControlService podControlService, Button button) {
        this.mPodControlService = podControlService;
        mTestView = new TestView(context);
        mDialogWrapper = DialogUtils.wrapper(mTestView);
        button.setVisibility(View.VISIBLE);
        button.setOnClickListener(v -> mDialogWrapper.show());

        mPodControlService.setBackgroundSwitchListener(on -> {
            mTestView.checkWithoutCallback(on);
            mTestView.textConsumer.accept("onBackgroundSwitched: on = [" + on + "] at " + DateFormat.getInstance().format(new Date()));
        });
        mPodControlService.setUserProfilePathListener((isSuccess, type)
                -> ToastUtils.showShort("isSuccess:" + isSuccess + " type :" + type));
    }

    private class TestView extends ScrollView {

        private final Consumer<CharSequence> textConsumer;
        private final SwitchCompat mSwitchCompat;
        private final EditText mEtAutoRecycleTime, mEtIdleTime;

        public TestView(Context context) {
            super(context);
            inflate(context, R.layout.dialog_pod_control, this);

            TextView text = findViewById(R.id.tv_info);

            textConsumer = charSequence -> {
                text.append(charSequence);
                text.append("\n");
            };

            mSwitchCompat = findViewById(R.id.switch_background);
            mSwitchCompat.setOnCheckedChangeListener(mOnCheckedChangeListener);

            mEtAutoRecycleTime = findViewById(R.id.et_auto_recycle_time);
            mEtIdleTime = findViewById(R.id.et_idle_time);

            /**
             * switchBackground(boolean on) -- 设置客户端应用或游戏切换前后台的状态
             *
             * @param on true -- 切后台
             *           false -- 切前台
             */
            findViewById(R.id.btn_background).setOnClickListener(view -> mPodControlService.switchBackground(true));
            findViewById(R.id.btn_foreground).setOnClickListener(view -> mPodControlService.switchBackground(false));

            /**
             * setIdleTime(long time) -- 设置客户端切后台之后，云端游戏的保活时间
             *
             * @param time 保活时长，单位秒
             */
            findViewById(R.id.btn_send_idle_time).setOnClickListener(v -> {
                int idleTime = 3 * 60;
                if (!TextUtils.isEmpty(mEtIdleTime.getText())) {
                    idleTime = Integer.parseInt(mEtIdleTime.getText().toString());
                }
                mPodControlService.setIdleTime(idleTime);
            });

            /**
             * setAutoRecycleTime(int time, SetAutoRecycleTimeCallback callback) -- 设置无操作回收服务时长
             *
             * @param time 无操作回收服务时长，单位秒
             * @param callback 设置无操作回收服务时长的回调
             * @return 0 -- 正常返回
             *        -1 -- 内部错误
             *        -2 -- time参数小于0
             */
            findViewById(R.id.btn_set_auto_recycle_time).setOnClickListener(v -> {
                int autoRecycleTime = 3 * 60;
                if (!TextUtils.isEmpty(mEtAutoRecycleTime.getText())) {
                    autoRecycleTime = Integer.parseInt(mEtAutoRecycleTime.getText().toString());
                }
                mPodControlService.setAutoRecycleTime(autoRecycleTime, new PodControlService.SetAutoRecycleTimeCallback() {
                    @Override
                    public void onResult(int i, long l) {
                        Log.d(TAG, "setAutoRecycleTimeResult" + i + "time" + l);
                        ToastUtils.showShort("setAutoRecycleTimeResult" + i + "time" + l);
                    }
                });
            });

            /**
             * getAutoRecycleTime(GetAutoRecycleTimeCallback callback) -- 查询无操作回收服务时长
             *
             * @param callback 查询无操作回收服务时长的回调
             * @return 0 -- 正常返回
             *        -1 -- 内部错误
             */
            findViewById(R.id.btn_get_auto_recycle_time).setOnClickListener(v -> {
                mPodControlService.getAutoRecycleTime(new PodControlService.GetAutoRecycleTimeCallback() {
                    @Override
                    public void onResult(int code, long time) {
                        Log.d(TAG, "getAutoRecycleTimeResult" + code + "time" + time);
                        ToastUtils.showShort("getAutoRecycleTimeResult" + code + "time" + time);
                    }
                });
            });

            /**
             * getUserProfilePath(GetUserProfilePathListener userProfilePathListener) -- 获取保存游戏云端配置文件的路径
             *
             * @param userProfilePathListener 获取保存游戏云端配置文件的路径的监听器
             * @return 0 -- 成功返回
             *         else -- 发生错误
             */
            findViewById(R.id.btn_getUserProfile).setOnClickListener(v -> {
                mPodControlService.getUserProfilePath(list -> {
                    ToastUtils.showShort(list.toString());
                });
            });

            /**
             * setUserProfilePath(String[] userProfilePath) -- 设置保存游戏云端配置文件的路径
             *
             * @param userProfilePath 保存配置文件的路径列表
             */
            findViewById(R.id.btn_setUserProfile).setOnClickListener(v -> {
                EditText editText = findViewById(R.id.et_user_profile_input);
                List<String> list = new ArrayList<>();
                list.add(editText.getText().toString());
                mPodControlService.setUserProfilePath(list);
            });

            TextView tv_snapshot_path = findViewById(R.id.tv_snapshot_path);
            ImageView iv_screen_shot = findViewById(R.id.iv_screen_shot);
            Switch saveOnPodScreenShot = findViewById(R.id.switch_save_on_pod);
            findViewById(R.id.btn_snapshot).setOnClickListener(v -> mPodControlService.screenShot(saveOnPodScreenShot.isChecked()));
            mPodControlService.setScreenShotListener(new PodControlService.ScreenShotListener() {
                @Override
                public void onScreenShot(int code, String savePath, String downloadUrl, String msg) {
                    Log.d(TAG, "onScreenShot: code = [" + code + "], savePath = [" + savePath + "], downloadUrl = [" + downloadUrl + "], msg = [" + msg + "]");
                    if (code == 0) {
                        tv_snapshot_path.setText(MessageFormat.format("savePath = [{0}]\n downloadUrl = [{1}]", savePath, downloadUrl));
//                        Glide.with(iv_screen_shot).load(downloadUrl).into(iv_screen_shot);
                    } else {
                        tv_snapshot_path.setText(MessageFormat.format("code = [{0}], msg = [{1}]", code, msg));
                    }
                }
            });

            EditText et_duration = findViewById(R.id.et_duration);
            et_duration.setText(String.valueOf(10));
            TextView tv_recording = findViewById(R.id.tv_recording);
            Switch saveOnPodScreenRecord = findViewById(R.id.is_saved_on_pod_screen_record);
            findViewById(R.id.btn_start_recording).setOnClickListener(v -> {
                int duration = 10;
                String etDuration = et_duration.getText().toString();
                if (!TextUtils.isEmpty(etDuration)) {
                    duration = Integer.parseInt(etDuration);
                }
                mPodControlService.startRecording(duration, saveOnPodScreenRecord.isChecked());
            });
            findViewById(R.id.btn_stop_recording).setOnClickListener(v -> {
                mPodControlService.stopRecording();
            });
            mPodControlService.setScreenRecordListener(new PodControlService.ScreenRecordListener() {
                @Override
                public void onRecordingStatus(int status, String savePath, String downloadUrl, String msg) {
                    Log.d(TAG, "onRecordingStatus: status = [" + status + "], savePath = [" + savePath + "], downloadUrl = [" + downloadUrl + "] + msg = [" + msg + "]");
                    tv_recording.setText(MessageFormat.format("status = [{0}], savePath = [{1}], downloadUrl = [{2}], msg = [{3}]", status, savePath, downloadUrl, msg));
                }
            });

        }

        boolean mWithoutCallback;

        void checkWithoutCallback(boolean check) {
            mWithoutCallback = true;
            mSwitchCompat.setChecked(check);
            mWithoutCallback = false;
        }

        final CompoundButton.OnCheckedChangeListener mOnCheckedChangeListener = new CompoundButton.OnCheckedChangeListener() {
            @Override
            public void onCheckedChanged(CompoundButton compoundButton, boolean isChecked) {
                if (mWithoutCallback) {
                    return;
                }
                mPodControlService.switchBackground(isChecked);
            }
        };
    }
}
