import { useCallback, useEffect, useRef, useState } from 'react';

export type VoiceState =
    | 'idle'
    | 'listening'
    | 'hearing'
    | 'transcribing'
    | 'thinking'
    | 'generating_audio'
    | 'speaking'
    | 'interrupted'
    | 'error';

interface Options {
    /** Send recorded audio to POST /voice/transcribe and return the text. */
    transcribe: (audio: Blob) => Promise<string>;
    /** Send text to POST /voice/tts and return the audio blob (mp3). */
    synthesize: (text: string) => Promise<Blob>;
    /** Called with each finished user utterance. Await your API call + `speak()` inside it. */
    onUtterance: (text: string) => Promise<void>;
    /** Called when fallback to browser speech synthesis occurs */
    onFallback?: (reason: string) => void;
    /** How long the user must stay silent before the turn ends (ms). */
    silenceMs?: number;
    /** Mic level (RMS 0..1) counted as speech. */
    speechThreshold?: number;
    /** Ignore clicks/noise shorter than this (ms). */
    minSpeechMs?: number;
}

const pickMime = () => {
    if (typeof MediaRecorder === 'undefined') return '';
    return ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4'].find((m) => MediaRecorder.isTypeSupported(m)) || '';
};

const splitSentences = (t: string) =>
    (t.replace(/[*#_•~`]/g, '').match(/[^.!؟?\n]+[.!؟?]?/g) || [])
        .map((s) => s.trim())
        .filter(Boolean);

export function useVoiceLoop(opts: Options) {
    const optsRef = useRef(opts);
    optsRef.current = opts;

    const [state, setState] = useState<VoiceState>('idle');
    const [level, setLevel] = useState(0);
    const [usingFallbackVoice, setUsingFallbackVoice] = useState(false);

    const runningRef = useRef(false);
    const streamRef = useRef<MediaStream | null>(null);
    const ctxRef = useRef<AudioContext | null>(null);
    const analyserRef = useRef<AnalyserNode | null>(null);
    const audioRef = useRef<HTMLAudioElement | null>(null);
    const playResolveRef = useRef<(() => void) | null>(null);
    const speakGenRef = useRef(0);
    const finishNowRef = useRef(false);

    /* ───────────── Unlock Browser Autoplay on First User Gesture ───────────── */
    const primeAudio = useCallback(() => {
        try {
            const AC = window.AudioContext || (window as any).webkitAudioContext;
            if (AC && (!ctxRef.current || ctxRef.current.state === 'suspended')) {
                const ctx = ctxRef.current || new AC();
                ctxRef.current = ctx;
                ctx.resume().catch(() => { });
            }
        } catch (e) {
            console.warn('AudioContext prime notice:', e);
        }
    }, []);

    /* ───────────── Browser SpeechSynthesis Fallback ───────────── */
    const speakWithBrowserSynthesis = (text: string): Promise<boolean> => {
        return new Promise((resolve) => {
            if (typeof window === 'undefined' || !('speechSynthesis' in window)) {
                return resolve(false);
            }
            try {
                window.speechSynthesis.cancel();
                const utterance = new SpeechSynthesisUtterance(text);
                const voices = window.speechSynthesis.getVoices();
                // Find Egyptian Arabic or any Arabic voice
                const arVoice = voices.find(
                    (v) => v.lang.toLowerCase().includes('ar-eg') || v.lang.toLowerCase().startsWith('ar')
                );
                if (arVoice) {
                    utterance.voice = arVoice;
                }
                utterance.lang = arVoice ? arVoice.lang : 'ar-EG';
                utterance.rate = 1.05;
                utterance.pitch = 1.0;

                const onDone = () => {
                    resolve(true);
                };
                utterance.onend = onDone;
                utterance.onerror = (e) => {
                    console.warn('SpeechSynthesis error:', e);
                    resolve(false);
                };
                setUsingFallbackVoice(true);
                optsRef.current.onFallback?.('جاري استخدام النطق المحلي للمتصفح كبديل احتياطي');
                window.speechSynthesis.speak(utterance);
            } catch (err) {
                console.warn('speechSynthesis exception:', err);
                resolve(false);
            }
        });
    };

    /* ───────────── Stop Speaking & Immediate Interruption ───────────── */
    const stopSpeaking = useCallback(() => {
        speakGenRef.current++;
        if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
            try {
                window.speechSynthesis.cancel();
            } catch { }
        }
        if (audioRef.current) {
            audioRef.current.pause();
            audioRef.current.currentTime = 0;
            audioRef.current = null;
        }
        if (playResolveRef.current) {
            playResolveRef.current();
            playResolveRef.current = null;
        }
        setUsingFallbackVoice(false);
    }, []);

    /* ───────────── Listening: one user turn, ends on silence ───────────── */
    const listenOneTurn = () =>
        new Promise<Blob | null>((resolve) => {
            const stream = streamRef.current!;
            const analyser = analyserRef.current!;
            const buf = new Uint8Array(analyser.fftSize);
            // speechThreshold 0.035: high enough to ignore background noise & AC,
            // low enough to catch normal speech. minSpeechMs 500ms filters out coughs/clicks.
            const { silenceMs = 1500, speechThreshold = 0.035, minSpeechMs = 500 } = optsRef.current;

            const mime = pickMime();
            // audioBitsPerSecond: 128kbps ensures Whisper receives high-quality audio.
            // Default browser quality (~32kbps) causes Whisper to hallucinate on Arabic speech.
            const rec = new MediaRecorder(
                stream,
                mime ? { mimeType: mime, audioBitsPerSecond: 128_000 } : { audioBitsPerSecond: 128_000 }
            );
            const chunks: Blob[] = [];
            rec.ondataavailable = (e) => e.data.size && chunks.push(e.data);
            rec.start(250);

            finishNowRef.current = false;
            let heard = false;
            let done = false;
            let speechStart = 0;
            let lastVoice = 0;
            const segStart = performance.now();
            setState('listening');

            const finish = (send: boolean) => {
                if (done) return;
                done = true;
                window.clearInterval(timer);
                rec.onstop = () =>
                    resolve(send ? new Blob(chunks, { type: rec.mimeType || 'audio/webm' }) : null);
                if (rec.state !== 'inactive') rec.stop();
                else resolve(null);
            };

            const timer = window.setInterval(() => {
                if (!runningRef.current) return finish(false);

                analyser.getByteTimeDomainData(buf);
                let sum = 0;
                for (let i = 0; i < buf.length; i++) {
                    const x = (buf[i] - 128) / 128;
                    sum += x * x;
                }
                const rms = Math.sqrt(sum / buf.length);
                setLevel(Math.min(100, Math.round(rms * 600)));

                const now = performance.now();
                if (rms > speechThreshold) {
                    if (!heard) {
                        heard = true;
                        speechStart = now;
                        setState('hearing');
                    }
                    lastVoice = now;
                }

                if (heard) {
                    const spoke = lastVoice - speechStart;
                    if (finishNowRef.current || now - lastVoice > silenceMs || now - speechStart > 60000) {
                        finish(spoke >= minSpeechMs);
                    }
                } else if (now - segStart > 4000) {
                    // Nothing said: restart the recorder so we never send long silent audio
                    finish(false);
                }
            }, 30);
        });

    /* ───────────── Main loop: listen → transcribe → onUtterance → repeat ───────────── */
    const cleanup = () => {
        streamRef.current?.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
        ctxRef.current?.close().catch(() => { });
        ctxRef.current = null;
        analyserRef.current = null;
        setLevel(0);
        setState('idle');
    };

    const start = useCallback(async () => {
        if (runningRef.current) return;
        runningRef.current = true;
        primeAudio();
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
            });
            streamRef.current = stream;

            const AC = window.AudioContext || (window as any).webkitAudioContext;
            const ctx = new AC();
            ctxRef.current = ctx;
            const analyser = ctx.createAnalyser();
            analyser.fftSize = 1024;
            ctx.createMediaStreamSource(stream).connect(analyser);
            analyserRef.current = analyser;

            while (runningRef.current) {
                const blob = await listenOneTurn();
                if (!blob || !runningRef.current) continue;

                setState('transcribing');
                let text = '';
                try {
                    text = (await optsRef.current.transcribe(blob)).trim();
                } catch (e) {
                    console.error('transcribe failed', e);
                }
                // Reject suspiciously short transcripts (< 4 chars) and known Whisper
                // hallucination phrases that appear when audio is silence or noise.
                const HALLUCINATION_PHRASES = [
                    'موسيقى', 'music', 'مرحباً', 'شكراً', 'شكرا', 'subscribe',
                    'اشترك', 'اشتركوا', 'للمزيد', 'like', 'تابعونا', 'ترجمة',
                    'استمر', 'تابع', 'يرجى', '...', '. . .', 'تفضل'
                ];
                const isHallucination =
                    text.length < 4 ||
                    HALLUCINATION_PHRASES.some(p => text.trim() === p || text.trim() === `${p}.`);
                if (isHallucination) {
                    console.debug(`[VoiceLoop] Discarded likely hallucination: "${text}"`);
                    continue;
                }

                setState('thinking');
                try {
                    await optsRef.current.onUtterance(text);
                } catch (e) {
                    console.error('onUtterance failed', e);
                }
            }
        } finally {
            runningRef.current = false;
            cleanup();
        }
    }, [primeAudio]);

    const stop = useCallback(() => {
        runningRef.current = false;
        stopSpeaking();
    }, [stopSpeaking]);

    /** Tap while the user is talking = "I'm done", skip the silence wait. */
    const finishTurn = useCallback(() => {
        finishNowRef.current = true;
    }, []);

    /* ───────────── Speaking: Play Audio Blob with Safe Verification ───────────── */
    const playBlob = (blob: Blob): Promise<boolean> =>
        new Promise<boolean>((resolve) => {
            if (!blob || blob.size < 200) {
                return resolve(false);
            }
            const url = URL.createObjectURL(blob);
            const a = new Audio(url);
            audioRef.current = a;
            let resolved = false;

            const done = (success: boolean) => {
                if (resolved) return;
                resolved = true;
                URL.revokeObjectURL(url);
                playResolveRef.current = null;
                audioRef.current = null;
                resolve(success);
            };

            playResolveRef.current = () => done(false);
            a.onended = () => done(true);
            a.onerror = () => done(false);

            a.play().catch((err) => {
                console.warn('Audio play rejected by browser autoplay policy:', err);
                done(false);
            });
        });

    const speak = useCallback(
        async (text: string) => {
            if (!text || !text.trim()) return;
            const parts = splitSentences(text);
            if (!parts.length) parts.push(text.trim());

            const gen = ++speakGenRef.current;
            setState('generating_audio');

            let serverAudioPlayed = false;

            // Try server-side synthesis
            try {
                const jobs = parts.map((p) => optsRef.current.synthesize(p));
                for (const job of jobs) {
                    if (gen !== speakGenRef.current) return;
                    try {
                        const blob = await job;
                        if (gen !== speakGenRef.current) return;
                        setState('speaking');
                        const ok = await playBlob(blob);
                        if (ok) {
                            serverAudioPlayed = true;
                        } else {
                            break;
                        }
                    } catch (e) {
                        console.warn('Server TTS piece failed:', e);
                        break;
                    }
                }
            } catch (err) {
                console.warn('Server TTS failed, activating fallback:', err);
            }

            // Fallback to browser Web Speech API if server audio was not played
            if (!serverAudioPlayed && gen === speakGenRef.current) {
                setState('speaking');
                await speakWithBrowserSynthesis(text);
            }

            if (gen === speakGenRef.current) {
                setUsingFallbackVoice(false);
                setState(runningRef.current ? 'thinking' : 'idle');
            }
        },
        []
    );

    useEffect(() => stop, [stop]);

    return {
        state,
        level,
        usingFallbackVoice,
        start,
        stop,
        finishTurn,
        speak,
        stopSpeaking,
        primeAudio,
    };
}