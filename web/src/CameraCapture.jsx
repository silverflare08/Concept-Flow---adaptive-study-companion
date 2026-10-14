import React, { useEffect, useRef, useState } from "react";
import { Camera, RotateCcw, Upload, X } from "lucide-react";

export default function CameraCapture({ onCapture, onClose }) {
  const video = useRef(null);
  const [photo, setPhoto] = useState(null);
  const [error, setError] = useState("");
  const [ready, setReady] = useState(false);
  useEffect(() => {
    let stream, cancelled = false;
    async function start() {
      try {
        if (!navigator.mediaDevices?.getUserMedia) throw new Error("Camera access needs localhost or HTTPS. You can also choose a photo below.");
        stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: "environment" }, width: { ideal: 1920 }, height: { ideal: 1080 } }, audio: false });
        if (cancelled) { stream.getTracks().forEach(track => track.stop()); return; }
        if (video.current) { video.current.srcObject = stream; await video.current.play(); }
      } catch (issue) { if (!cancelled) setError(issue.name === "NotAllowedError" ? "Camera permission was denied. Allow camera access in your browser or choose a photo below." : issue.message); }
    }
    start();
    return () => { cancelled = true; stream?.getTracks().forEach(track => track.stop()); };
  }, []);
  useEffect(() => { function escape(e) { if (e.key === "Escape") onClose(); } document.addEventListener("keydown", escape); return () => document.removeEventListener("keydown", escape); }, [onClose]);
  function capture() {
    if (!video.current?.videoWidth || !video.current?.videoHeight || video.current.readyState < 2) {
      setError("The camera is still focusing. Wait for the live image and try again.");
      return;
    }
    setError("");
    const canvas = document.createElement("canvas");
    canvas.width = video.current.videoWidth; canvas.height = video.current.videoHeight;
    canvas.getContext("2d").drawImage(video.current, 0, 0);
    canvas.toBlob(blob => { if (blob && blob.size) setPhoto(blob); else setError("Could not capture this frame. Please retake the photo."); }, "image/jpeg", 0.95);
  }
  const [preview, setPreview] = useState("");
  useEffect(() => { if (!photo) { setPreview(""); return; } const url = URL.createObjectURL(photo); setPreview(url); return () => URL.revokeObjectURL(url); }, [photo]);
  function usePhoto() { onCapture(new File([photo], `handwritten-notes-${Date.now()}.jpg`, { type: "image/jpeg" })); onClose(); }
  return <div className="fixed inset-0 z-50 grid place-items-center bg-slate-900/35 p-4 backdrop-blur-sm"><section role="dialog" aria-modal="true" aria-label="Take a photo" className="w-full max-w-xl rounded-3xl bg-[#fbfaff] p-5 shadow-2xl"><div className="flex items-center justify-between"><h2 className="flex items-center gap-2 text-lg font-bold"><Camera size={20} className="text-plum"/>Take a photo</h2><button onClick={onClose} aria-label="Close camera" className="icon-button"><X size={18}/></button></div><p className="mt-2 text-xs text-slate-500">Keep the complete page in view, with good lighting and sharp handwriting.</p><div className="mt-4 overflow-hidden rounded-2xl bg-slate-100"><video ref={video} autoPlay playsInline muted onLoadedMetadata={() => setReady(true)} className={`max-h-[50vh] w-full ${photo ? "hidden" : ""}`}/>{preview && <img src={preview} alt="Your captured handwritten notes" className="max-h-[50vh] w-full object-contain"/>}</div>{error && <p role="alert" className="mt-3 rounded-xl bg-peach p-3 text-xs">{error}</p>}<div className="mt-4 flex flex-wrap gap-2">{photo ? <><button onClick={() => setPhoto(null)} className="secondary-button"><RotateCcw size={15}/>Retake</button><button onClick={usePhoto} className="primary-button"><Upload size={15}/>Use photo</button></> : <button disabled={!ready} onClick={capture} className="primary-button disabled:opacity-50"><Camera size={15}/>Capture photo</button>}<label className="secondary-button cursor-pointer">Choose / take a phone photo<input type="file" accept="image/*" capture="environment" className="hidden" onChange={e => { const file = e.target.files?.[0]; if (file) { onCapture(file); onClose(); } }}/></label></div><p className="mt-3 text-[11px] text-slate-400">Your photo is added to the upload list. Select Upload and prepare to read it.</p></section></div>;
}
