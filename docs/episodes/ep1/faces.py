import cv2, json
cap = cv2.VideoCapture("src.mp4")
fps = cap.get(cv2.CAP_PROP_FPS); W=int(cap.get(3)); H=int(cap.get(4))
det = cv2.FaceDetectorYN.create("yunet.onnx","",(W,H),0.6,0.3,5000)
out=[]; i=0; step=int(fps/4)
while True:
    ok = cap.grab()
    if not ok: break
    if i%step==0:
        ok, f = cap.retrieve()
        _, faces = det.detect(f)
        fl=[]
        if faces is not None:
            for x in faces: fl.append([float(x[0])/W,float(x[1])/H,float(x[2])/W,float(x[3])/H,float(x[14])])
        out.append({"t":i/fps,"faces":fl})
    i+=1
json.dump(out,open("faces.json","w"))
print(len(out), sum(1 for o in out if o["faces"]))
