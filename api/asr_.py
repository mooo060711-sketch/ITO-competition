import os
import tempfile
from fastapi import APIRouter, UploadFile, File, HTTPException
from faster_whisper import WhisperModel

router = APIRouter(prefix="/api/v1")

print("🎙️ 正在加载 faster-whisper 语音识别模型...")
    # 若无独立显卡，自动回退到 CPU 模式
whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
print("✅ 语音模型 (CPU) 加载完毕！")

@router.post("/asr")
async def transcribe_audio(file: UploadFile = File(...)):
    """接收前端录音文件并进行语音转写"""
    try:
        # 1. 创建临时文件保存前端传来的音频流
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_audio:
            content = await file.read()
            temp_audio.write(content)
            temp_audio_path = temp_audio.name

        # 2. 调用 faster-whisper 进行语音转写 (强制中文)
        segments, info = whisper_model.transcribe(temp_audio_path, beam_size=5, language="zh")
        text = "".join([segment.text for segment in segments])

        # 3. 清理临时音频文件，释放磁盘空间
        os.remove(temp_audio_path)

        return {"code": 200, "text": text.strip()}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"语音识别异常: {str(e)}")
