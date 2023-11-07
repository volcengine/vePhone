package com.example.sdkdemo.feature;

import android.Manifest;
import android.annotation.SuppressLint;
import android.content.Context;
import android.location.LocationManager;
import android.os.Looper;
import android.util.Log;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.RadioGroup;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.widget.SwitchCompat;

import com.blankj.utilcode.util.PermissionUtils;
import com.blankj.utilcode.util.ToastUtils;
import com.example.sdkdemo.R;
import com.example.sdkdemo.util.DialogUtils;
import com.volcengine.cloudphone.apiservice.LocationService;

import java.text.DateFormat;
import java.util.Date;
import java.util.Locale;

public class LocationServiceView {

    LocationService mLocationService;
    private DialogUtils.DialogWrapper mDialogWrapper;
    private static final String TAG = "LocationServiceView";

    public LocationServiceView(Context context, LocationService locationService, Button button) {
        this.mLocationService = locationService;
        mDialogWrapper = DialogUtils.wrapper(new TestView(context));
        button.setVisibility(View.VISIBLE);
        button.setOnClickListener(v -> mDialogWrapper.show());
    }

    private class TestView extends ScrollView implements LocationService.LocationEventListener {
        private final TextView mTvLocation;
        private final TextView tv_log;

        public TestView(Context context) {
            super(context);
            inflate(context, R.layout.dialog_location, this);
            tv_log = findViewById(R.id.tv_log);
            mTvLocation = findViewById(R.id.tv_location);

            /**
             * isLocationServiceEnabled() -- 是否开启定位服务
             * enableLocationService(boolean enable) -- 定位服务开关
             */
            SwitchCompat switchCompat = findViewById(R.id.switch_enable);
            switchCompat.setChecked(mLocationService.isLocationServiceEnabled());
            switchCompat.setOnCheckedChangeListener((buttonView, isChecked) -> mLocationService.enableLocationService(isChecked));

            /**
             * setLocationEventListener(LocationEventListener listener) -- 设置定位事件监听器
             */
            SwitchCompat switchListener = findViewById(R.id.switch_listener);
            mLocationService.setLocationEventListener(this);
            switchListener.setChecked(true);
            switchListener.setOnCheckedChangeListener((buttonView, isChecked) -> mLocationService.setLocationEventListener(isChecked ? this : null));

            /**
             * setRemoteLocationMock(LocationInfo location) -- 更新远端实例位置信息
             *
             * @param location 位置信息
             */
            findViewById(R.id.btn_setRemoteLocation).setOnClickListener(v -> requestLocationAndSet(true));
            EditText et_lat = findViewById(R.id.et_lat);
            EditText et_long = findViewById(R.id.et_long);
            findViewById(R.id.btn_setRemoteLocation2).setOnClickListener(v -> {
                try {
                    double lng = Double.parseDouble(et_long.getText().toString());
                    double lat = Double.parseDouble(et_lat.getText().toString());
                    mLocationService.setRemoteLocationMock(new LocationService.LocationInfo(lat, lng));
                } catch (NumberFormatException e) {
                    ToastUtils.showShort("输入合法小数");
                }
            });

            /**
             * setLocationServiceMode(int mode) -- 设置定位服务模式
             *
             * @param mode 定位服务模式
             *             MODE_AUTO(0) -- 自动模式，当收到远端实例指令时自动获取定位上报并触发回调
             *                              {@link LocationService.LocationEventListener#onSentLocalLocation(LocationService.LocationInfo)}
             *             MODE_MANUAL(1) -- 手动模式，当收到远端实例指令时触发回调
             *                              {@link LocationService.LocationEventListener#onReceivedRemoteLocationRequest(LocationService.RequestOptions)}
             *                              以及{@link LocationService.LocationEventListener#onRemoteLocationRequestEnded()}
             */
            RadioGroup rg_mode = findViewById(R.id.rg_mode);
            rg_mode.check(mLocationService.getLocationServiceMode() == LocationService.MODE_AUTO ? R.id.rb_auto : R.id.rb_manual);
            rg_mode.setOnCheckedChangeListener((group, checkedId) ->
                    mLocationService.setLocationServiceMode(checkedId == R.id.rb_auto ? LocationService.MODE_AUTO : LocationService.MODE_MANUAL));

        }

        /**
         * 收到远端实例位置请求的回调
         *
         * @param options 位置请求选项
         */
        @Override
        public void onReceivedRemoteLocationRequest(LocationService.RequestOptions options) {
            Log.d(TAG, "onReceivedRemoteLocationRequest: ");
            tv_log.append("==> onRemoteLocationRequest: " + options + "\n\n");
            requestLocationAndSet(false);
        }

        /**
         * 远端实例定位请求停止
         */
        @Override
        public void onRemoteLocationRequestEnded() {
            Log.d(TAG, "onRemoteLocationRequestEnded: ");
            tv_log.append("==> onStopRemoteLocationRequest: " + DateFormat.getInstance().format(new Date()) + "\n\n");
        }

        /**
         * 在自动定位模式下，向远端实例发送本地设备位置信息后的回调
         *
         * @param location 发送到云端实例的本地设备位置信息
         */
        @Override
        public void onSentLocalLocation(LocationService.LocationInfo location) {
            Log.d(TAG, "onSentLocalLocation: ");
            tv_log.append("==> onSentLocalLocation: " + location + "\n\n");
        }

        /**
         * 远端实例位置更新后的回调
         * 当手动调用{@link LocationService#setRemoteLocationMock(LocationService.LocationInfo)}时触发该回调；
         * 当设置为自动获取或者没有调用{@link LocationService#setRemoteLocationMock(LocationService.LocationInfo)}的时候不会触发。
         *
         * @param location 远端实例更新的位置信息
         */
        @Override
        public void onRemoteLocationUpdated(LocationService.LocationInfo location) {
            Log.d(TAG, "onRemoteLocationUpdated: ");
            tv_log.append("==> onRemoteLocationUpdated() called with: location = [" + location + "]" + "\n\n");
        }

        private void requestLocationAndSet(boolean manual) {
            PermissionUtils.permission(Manifest.permission.ACCESS_FINE_LOCATION)
                    .callback(new PermissionUtils.SimpleCallback() {
                        @SuppressLint("MissingPermission")
                        @Override
                        public void onGranted() {
                            LocationManager lm = (LocationManager) getContext().getSystemService(Context.LOCATION_SERVICE);
                            lm.requestSingleUpdate(LocationManager.NETWORK_PROVIDER, location -> {
                                if (manual) {
                                    mTvLocation.setText(String.format(
                                            Locale.getDefault(),
                                            "客户端的坐标是：\nlat[%f], long[%f]",
                                            location.getLatitude(),
                                            location.getLongitude()));
                                }
                                mLocationService.setRemoteLocationMock(new LocationService.LocationInfo(
                                        location.getLatitude(),
                                        location.getLongitude()
                                ));
                            }, Looper.getMainLooper());
                        }

                        @Override
                        public void onDenied() {
                            Toast.makeText(getContext(), "无定位权限", Toast.LENGTH_SHORT).show();
                        }
                    })
                    .request();
        }

    }
}
