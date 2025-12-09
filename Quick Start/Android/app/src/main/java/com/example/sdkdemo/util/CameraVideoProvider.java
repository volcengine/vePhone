package com.example.sdkdemo.util;

import android.Manifest;
import android.content.Context;
import android.graphics.ImageFormat;
import android.graphics.SurfaceTexture;
import android.hardware.Camera;
import android.os.Handler;
import android.os.HandlerThread;
import android.util.Log;
import android.view.Display;
import android.view.Surface;
import android.view.WindowManager;

import androidx.annotation.RequiresPermission;
import androidx.core.util.Consumer;

import com.volcengine.cloudcore.common.mode.CameraId;
import com.volcengine.cloudphone.base.VeVideoFrame;

import java.nio.ByteBuffer;

public class CameraVideoProvider implements Camera.PreviewCallback {

    private static final String TAG = "CameraVideoProvider";
    private Camera.Size mPreviewSize;
    private volatile Camera mCamera;
    private int mYuvBufferSize;
    private byte[] mI420Data, mRotateData;
    private SurfaceTexture mSurfaceTexture;
    private Consumer<VeVideoFrame> mFrameConsumer;
    private int mCameraId = Camera.CameraInfo.CAMERA_FACING_BACK;
    private volatile VeVideoFrame mVideoFrame;
    private volatile HandlerThread mPushStreamThread;
    private volatile Handler mPushStreamHandler;
    private Context mContext;


    public CameraVideoProvider(Context context) {
        mContext = context;
    }

    @RequiresPermission(Manifest.permission.CAMERA)
    public void start(CameraId cameraId){
        if (mPushStreamThread != null) {
            stopPushThread();
        }
        mCameraId = cameraId == CameraId.FRONT ?
                Camera.CameraInfo.CAMERA_FACING_FRONT : Camera.CameraInfo.CAMERA_FACING_BACK;
        mPushStreamThread = new HandlerThread("PushStreamThread");
        mPushStreamThread.start();
        mPushStreamHandler = new Handler(mPushStreamThread.getLooper());
        mPushStreamHandler.post(() -> {
            if (initCamera()) {
                mCamera.startPreview();
            }
        });
    }

    @Override
    public void onPreviewFrame(byte[] data, Camera camera) {
        if (isStopped()) {
            Log.w(TAG, "onPreviewFrame: already stopped ignore frame");
            return;
        }
        mPushStreamHandler.post(() -> {
            final Camera camera1 = mCamera;
            if (isStopped() || camera1 == null) {
                Log.w(TAG, "onPreviewFrame: double check already stopped ignore frame");
                return;
            }
            nv21ToI420(data, mI420Data, mPreviewSize.width, mPreviewSize.height);
            updateVideoFrame(mVideoFrame, mI420Data);

            if (mFrameConsumer != null) {
                mFrameConsumer.accept(mVideoFrame);
            }
            // 重新设置监听
            camera1.addCallbackBuffer(data);
        });
    }

    public void setFrameConsumer(Consumer<VeVideoFrame> consumer) {
        mFrameConsumer = consumer;
    }

    public void stop() {
        if (mCamera != null) {
            mCamera.stopPreview();
            mCamera.release();
            mCamera = null;
        }
        if (mSurfaceTexture != null) {
            mSurfaceTexture.release();
            mSurfaceTexture = null;
        }
        stopPushThread();
        mFrameConsumer = null;
        mVideoFrame = null;
    }

    public boolean isStopped(){
        if (mCamera == null) {
            return true;
        }
        if (mVideoFrame == null) {
            return true;
        }
        return mPushStreamHandler == null || mPushStreamThread == null || !mPushStreamThread.isAlive();
    }

    public void switchCamera(){
        mCamera.setPreviewCallback(null);
        mCamera.stopPreview();
        mCamera.release();
        if (mCameraId == Camera.CameraInfo.CAMERA_FACING_FRONT) {
            mCameraId = Camera.CameraInfo.CAMERA_FACING_BACK;
        } else {
            mCameraId = Camera.CameraInfo.CAMERA_FACING_FRONT;
        }
        if (initCamera()) {
            mCamera.startPreview();
        }
    }

    private boolean initCamera() {
        try {
            mCamera = Camera.open(mCameraId);
            mCamera.setErrorCallback(new Camera.ErrorCallback() {
                @Override
                public void onError(int error, Camera camera) {
                    Log.w(TAG, "onError: " + error);
                }
            });
            setCameraDisplayOrientation();
            Camera.Parameters parameters = mCamera.getParameters();
            mPreviewSize = parameters.getPreviewSize();
            Camera.Size pictureSize = parameters.getPictureSize();
            if (!mPreviewSize.equals(pictureSize)) {
                parameters.setPictureSize(mPreviewSize.width, mPreviewSize.height);
            }
            // ImageFormat与YUV类型关系：android.hardware.Camera.Parameters#cameraFormatForPixelFormat
            parameters.setPreviewFormat(ImageFormat.NV21);
            if (mCameraId == Camera.CameraInfo.CAMERA_FACING_BACK) {
                parameters.setFocusMode(Camera.Parameters.FOCUS_MODE_CONTINUOUS_VIDEO);
            }
            parameters.setPreviewFrameRate(25);
            mCamera.setParameters(parameters);

            mYuvBufferSize = (int) (mPreviewSize.width * mPreviewSize.height * 3 / 2 + 0.5f);
            if (mSurfaceTexture == null) {
                mSurfaceTexture = new SurfaceTexture(0);
            }
            mCamera.setPreviewTexture(mSurfaceTexture);
            byte[] nv21Buffer = new byte[mYuvBufferSize];
            mI420Data = new byte[mYuvBufferSize];
            mRotateData = new byte[mYuvBufferSize];
            mVideoFrame = createVideoFrame(mPreviewSize.width, mPreviewSize.height);

            mCamera.addCallbackBuffer(nv21Buffer);
            mCamera.setPreviewCallbackWithBuffer(CameraVideoProvider.this);
            return true;
        } catch (Exception e) {
            Log.e(TAG, "start: " + Log.getStackTraceString(e));
            return false;
        }
    }


    private void stopPushThread() {
        if (mPushStreamHandler != null) {
            mPushStreamHandler.removeCallbacksAndMessages(null);
            mPushStreamHandler = null;
        }
        if (mPushStreamThread != null) {
            if (mPushStreamThread.isAlive()) {
                mPushStreamThread.quit();
            }
            mPushStreamThread = null;
        }
    }

    private void updateVideoFrame(VeVideoFrame frame, byte[] bytes){
        frame.timestamp = System.currentTimeMillis();
        if (frame.buffer == null || frame.buffer.capacity() != bytes.length) {
            frame.buffer = ByteBuffer.allocateDirect(bytes.length);
        }
        frame.buffer.clear();
        frame.buffer.put(bytes);
        frame.buffer.flip();
//            Log.d(TAG, MessageFormat.format(
//                    // position=0,limit=83,capacity=48,400
//                    "updateVideoFrame: position={0}, limit={1}, capacity={2}, length={3}",
//                    frame.buffer.position(),
//                    frame.buffer.limit(),
//                    frame.buffer.capacity(),
//                    bytes.length
//            ));
    }


    private VeVideoFrame createVideoFrame(int width, int height) {
        Log.d(TAG, "createVideoFrame: width=" + width + ", height=" + height + "");
        VeVideoFrame frame = new VeVideoFrame();
        frame.format = VeVideoFrame.PixelFormat.I420;
        if (mCameraId == Camera.CameraInfo.CAMERA_FACING_FRONT) {
            frame.rotation = VeVideoFrame.VideoRotation.VIDEO_ROTATION_270;
        } else {
            Camera.CameraInfo info = new Camera.CameraInfo();
            Camera.getCameraInfo(mCameraId, info);
            frame.rotation = info.orientation;
        }
        frame.width = width;
        frame.height = height;
        frame.stride = width;
        return frame;
    }

    private void setCameraDisplayOrientation(){
        int degrees = getDisplayRotationDegree(mContext);
        Camera.CameraInfo info = new Camera.CameraInfo();
        Camera.getCameraInfo(mCameraId, info);
        int result;
        if (info.facing == Camera.CameraInfo.CAMERA_FACING_FRONT) {
            result = (info.orientation + degrees) % 360;
            result = (360 - result) % 360;  // compensate the mirror
        } else {  // back-facing
            result = (info.orientation - degrees + 360) % 360;
        }
        mCamera.setDisplayOrientation(result);
    }

    private int getDisplayRotationDegree(Context context) {
        Display display = ((WindowManager) context.getSystemService(Context.WINDOW_SERVICE)).getDefaultDisplay();
        switch (display.getRotation()) {
            case Surface.ROTATION_0:
                return VeVideoFrame.VideoRotation.VIDEO_ROTATION_0;
            case Surface.ROTATION_90:
                return VeVideoFrame.VideoRotation.VIDEO_ROTATION_90;
            case Surface.ROTATION_180:
                return VeVideoFrame.VideoRotation.VIDEO_ROTATION_180;
            case Surface.ROTATION_270:
                return VeVideoFrame.VideoRotation.VIDEO_ROTATION_270;
        }
        throw new IllegalStateException("never reach");
    }

    private static byte[] nv21ToI420(byte[] data, byte[] ret, int width, int height) {
        int total = width * height;

        ByteBuffer bufferY = ByteBuffer.wrap(ret, 0, total);
        ByteBuffer bufferU = ByteBuffer.wrap(ret, total, total / 4);
        ByteBuffer bufferV = ByteBuffer.wrap(ret, total + total / 4, total / 4);

        bufferY.put(data, 0, total);
        for (int i = total; i < data.length; i += 2) {
            bufferV.put(data[i]);
            bufferU.put(data[i + 1]);
        }
        return ret;
    }
}
