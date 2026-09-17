#!/usr/bin/env python3
"""두루마리 중심축을 찾고 격자점의 감긴 횟수를 매긴다."""
import sys, numpy as np, tifffile, os
sys.path.insert(0,'/Users/parksik/seamcheck')

def load(d):
    X,Y,Z=(tifffile.imread(os.path.join(d,f"{c}.tif")) for c in "xyz")
    P=np.stack([X,Y,Z],-1).astype(np.float64); v=(X>=0)&(Y>=0)&(Z>=0)
    return P,v

P,v=load(sys.argv[1] if len(sys.argv)>1 else '/Users/parksik/scroll/sample_tifxyz')
pts=P[v]
print(f"유효점 {len(pts):,}")

# 두루마리 축은 대체로 수직(z). 주성분으로 확인한다.
c=pts.mean(0); A=pts-c
u,s,vt=np.linalg.svd(A[::37], full_matrices=False)
print("주성분 분산비:", (s**2/np.sum(s**2)).round(3))
print("제1축:", vt[0].round(3), "| 제3축(가장 납작한 방향):", vt[2].round(3))

# 축 후보: 데이터가 가장 길게 뻗은 방향
axis=vt[0]/np.linalg.norm(vt[0])
print("\n축을 제1주성분으로 두고 각도를 재본다")
e1=np.array([1.0,0,0]); e1=e1-axis*np.dot(e1,axis); e1/=np.linalg.norm(e1)
e2=np.cross(axis,e1)
def ang(p):
    q=p-c
    return np.arctan2(q@e2, q@e1)
# u 방향(격자 가로)을 따라 각도가 단조로 도는지
H,W=v.shape
row=H//2
sel=[x for x in range(W) if v[row,x]]
if len(sel)>50:
    a=np.unwrap(np.array([ang(P[row,x]) for x in sel]))
    turns=(a.max()-a.min())/(2*np.pi)
    print(f"가운데 행에서 각도 변화: {turns:.2f} 바퀴  ({len(sel)}점)")
    d=np.diff(a)
    print(f"  한 칸당 각도 변화: 중앙 {np.median(d)*180/np.pi:.3f}° · 최대 {np.abs(d).max()*180/np.pi:.2f}°")
    print(f"  부호 뒤집힘(되감김) 횟수: {int((np.sign(d[:-1])!=np.sign(d[1:])).sum())}")
