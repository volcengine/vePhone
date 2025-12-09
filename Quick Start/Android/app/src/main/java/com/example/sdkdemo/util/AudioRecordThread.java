package com.example.sdkdemo.util;

import android.media.AudioFormat;
import android.media.AudioRecord;
import android.media.MediaRecorder;
import android.util.Log;

import androidx.annotation.RequiresPermission;

import com.volcengine.cloudcore.common.mode.AudioSourceType;
import com.volcengine.cloudcore.common.mode.StreamIndex;
import com.volcengine.cloudphone.apiservice.AudioService;
import com.volcengine.cloudphone.base.VeAudioFrame;

import java.nio.ByteBuffer;

public class AudioRecordThread extends Thread {
    private static final String TAG = "AudioRecordThread";
    private final AudioRecord mAudioRecord;
    private static final int sampleRateInHz = VeAudioFrame.VeAudioSampleRate.AUDIO_SAMPLE_RATE_48000.value;
    private static final int samples = sampleRateInHz / 100;
    private static final int channelConfig = AudioFormat.CHANNEL_IN_MONO;
    private static final int audioFormat = AudioFormat.ENCODING_PCM_16BIT;
    private final int bufferSizeInBytes;
    private volatile boolean recording = true;
    private final AudioService mAudioService;

    @RequiresPermission(android.Manifest.permission.RECORD_AUDIO)
    public AudioRecordThread(AudioService audioService) {
        super("AudioRecordThread");
        mAudioService = audioService;
        if (channelConfig == AudioFormat.CHANNEL_IN_MONO) {
            bufferSizeInBytes = samples * 2;
        } else {
            bufferSizeInBytes = samples * 2 * 2;
        }
        mAudioRecord = new AudioRecord(
                MediaRecorder.AudioSource.MIC,
                sampleRateInHz,
                channelConfig,
                audioFormat,
                bufferSizeInBytes
        );
    }

    public void setRecordStatus(boolean enable) {
        recording = enable;
    }

    @Override
    public void run() {
        if (mAudioService == null) {
            return;
        }
        /**
         * (外部采集使用)
         * 设置本地音频源类型
         * int setAudioSourceType(int index, int type)
         *
         * @param index 音频流索引
         *              0 -- 主流
         *              1 -- 屏幕流
         * @param type 音频源类型
         *             0 -- 外部采集音频源(自定义采集)
         *             1 -- 内部采集音频源(本地麦克风采集)
         *
         * @return 0 -- 调用成功
         *        -1 -- 调用失败
         *
         *
         * 发布本地音频，音频外部采集需要调用此接口
         * int publishLocalAudio()
         *
         * @return 0 -- 调用成功
         *        -1 -- 调用失败
         */
        mAudioService.setAudioSourceType(StreamIndex.MAIN, AudioSourceType.EXTERNAL);
        mAudioService.publishLocalAudio();
        try {
            mAudioRecord.startRecording();
            byte[] audioBuffer = new byte[bufferSizeInBytes];
            Log.d(TAG, "AudioRecordThread: start");
            int offset = 0;
            int ret = 0;
            VeAudioFrame frame = new VeAudioFrame(
                    0,
                    VeAudioFrame.VeAudioSampleRate.AUDIO_SAMPLE_RATE_48000,
                    VeAudioFrame.VeAudioChannel.AUDIO_CHANNEL_MONO,
                    ByteBuffer.allocateDirect(bufferSizeInBytes),
                    0,
                    VeAudioFrame.VeAudioFrameType.FRAME_TYPE_PCM16
            );
            outer:
            while (recording) {
                offset = 0;
                long startTime = System.currentTimeMillis();
                while (offset < bufferSizeInBytes && recording) {
                    ret = mAudioRecord.read(audioBuffer, offset,bufferSizeInBytes - offset);
                    if (ret < 0) {
                        break outer;
                    }
                    offset += ret;
                }
                if (recording) {
                    // Now we got audio frame data, deal with it.
                    frame.timestamp_us = startTime;
                    frame.dataSize = bufferSizeInBytes;
                    frame.dataBuffer.clear();
                    frame.dataBuffer.put(audioBuffer);
                    frame.dataBuffer.flip();
                    /**
                     * 向云端实例推送外部采集音频源(需要先调用 setAudioSourceType，将采集模式设置为外部采集音频源，然后调用 publishLocalAudio 发布本地音频)
                     * int pushExternalAudioFrame(int index, VeAudioFrame frame)
                     *
                     * @param index 音频流索引
                     * @param frame 外部采集的音频帧
                     *
                     * @return 0 -- 调用成功
                     *        -1 -- 调用失败
                     */
                    mAudioService.pushExternalAudioFrame(StreamIndex.MAIN, frame);
                }
            }
        } finally {
            mAudioRecord.stop();
            /**
             * (外部采集使用)
             * 取消发布本地音频，音频外部采集需要调用此接口
             * int unpublishLocalAudio()
             *
             * @return 0 -- 调用成功
             *        -1 -- 调用失败
             */
            mAudioService.unpublishLocalAudio();
            mAudioService.setAudioSourceType(StreamIndex.MAIN, AudioSourceType.INTERNAL);
            Log.d(TAG, "AudioRecordThread: stop");
        }
    }
}
