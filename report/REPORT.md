# Báo cáo Day 6: Phát hiện suy giảm LiDAR bằng mật độ góc quét

- **Họ tên:** Nguyễn Đức Anh
- **MSSV:** 2A202602625
- **Lớp:** AI20K-T4
- **Link repo:** https://github.com/Munfond/NguyenDucAnh-2A202602625-Track4-Day21
- **Topic:** E — Data health dashboard (mục tiêu Advanced)
- **Dataset:** data/synthetic (debug và kiểm tra lỗi); data/kitti_mini và data/nuscenes_mini_subset (thí nghiệm chính).
- **Các frame đã dùng:** 105 frame đã được thống kê; 100 frame thật dùng cho benchmark:
  - Synthetic: 000000, 000001, 000002, 000003, 000004.
  - KITTI: 000001, 000004, 000007, 000008, 000009, 000010, 000011, 000012, 000015, 000016, 000019, 000021, 000023, 000025, 000031, 000032, 000043, 000048, 000049, 000061.
  - nuScenes: scene-0103_000 đến scene-0103_039 và scene-1094_000 đến scene-1094_039 (đủ 80 frame).

## 1. Claim

**Kết luận cuối:** trên tập test KITTI, score dùng ô góc xấu nhất ở ngưỡng 0,4 phát hiện 100% dropout 50% và sector dropout 30°, báo trên gốc 10%; trên nuScenes, ngưỡng 0,6 vẫn báo trên gốc 80%, nên cách này chưa dùng được như bộ phân loại lỗi sensor chung.
**Claim ban đầu:** phát hiện ≥90% hai loại suy giảm mạnh với báo nhầm ≤10% trên cả hai dataset; **bị bác bỏ** trên nuScenes trong các ngưỡng đã khảo sát (0,2/0,4/0,6).
Thí nghiệm có 20 frame KITTI và 80 nuScenes, random dropout 0/10/30/50%, sector dropout 0/10/20/30°, seed 42; test gồm 10/40 frame lẻ, calibration gồm 10/40 frame chẵn (nuScenes chia riêng từng scene).
Reference fit và chọn ngưỡng chỉ từ calibration; frame liền kề nên chưa chứng minh tổng quát sang scene mới. “Báo nhầm” ở đây coi frame gốc là đối chứng âm, không khẳng định mọi frame gốc sạch lỗi sensor.

## 2. Evidence

700 cấu hình dữ liệu × 3 ngưỡng = 2.100 dòng cảnh báo; score = clip(max(1−n/reference_n, max_bin(1−bin/reference_bin)),0,1), reference median trên calibration, cảnh báo khi score > ngưỡng. nuScenes không có ngưỡng đạt báo trên calibration ≤10%; 0,6 là fallback.

| Dataset / cách | Ngưỡng | Báo trên gốc | Phát hiện random 50% | Phát hiện sector 30° |
|---|---:|---:|---:|---:|
| KITTI / worst_bin | 0,4 | 1/10 (10%) | 10/10 (100%) | 10/10 (100%) |
| nuScenes / worst_bin | 0,6 fallback | 32/40 (80%) | 40/40 (100%) | 40/40 (100%) |
| KITTI / global_count | 0,2 | 0/10 (0%) | 10/10 (100%) | 0/10 (0%) |
| nuScenes / global_count | 0,2 | 0/40 (0%) | 40/40 (100%) | 0/40 (0%) |

![Thí nghiệm ngưỡng và suy giảm](../results/figures/health_threshold_sweep.png)
KITTI tăng ngưỡng 0,2 → 0,6 giảm báo trên gốc 50% → 0% nhưng phát hiện random 50% giảm 100% → 60%; nuScenes giảm báo trên gốc 97,5% → 80%. Không kết luận khác biệt là do riêng ngày/đêm.
Dashboard đầy đủ có histogram range/intensity, azimuth/elevation, số điểm, invalid và ranking review; nuScenes hai scene có gap trung vị 0,499876/0,499885 s, synthetic 000003 có gap 0,2 s thay vì 0,1 s. CSV và ba dashboard ở [bằng chứng chi tiết](EVIDENCE_DETAILS.md#dashboard-đầy-đủ-và-ranking).
![Dashboard nuScenes](../results/figures/dashboard_nuscenes_mini_subset_final.png)
**[B1]** Hai cách trên cùng input/split/reference/metric: global_count ít báo trên gốc nhưng bỏ sót sector; worst_bin bắt sector nhưng nhạy với cảnh. Ba CSV so sánh chạy lại giống từng byte; [bảng, plot và failure](EVIDENCE_DETAILS.md).
**[B2]** Hai loại suy giảm × ba mức ngoài baseline, dùng `starter.perturb`, giữ seed 42; plot trên và `health_scores.csv`/`health_threshold_sweep.csv` là bằng chứng, năm CSV CP3 chạy lại giống từng byte.
**[B3]** Mỗi dataset/cách bỏ một warmup, đo 30 lần: 120 dòng `health_latency.csv`. Worst_bin p50/p95 KITTI = 6,560/8,233 ms, nuScenes = 3,949/4,789 ms; i5-13420H, RAM 15,7 GB, chạy CPU. Chỉ tính trích metric → flag trên điểm trong RAM; bỏ I/O, fit reference, perturbation và plot, timing thay đổi theo tải máy.
Bonus đề nghị B1+B2+B3+B4 = 12, trần +10; không đề nghị B5 (trùng Advanced E) hoặc B6 (chưa xác minh mọi lỗi synthetic). Điểm thực tế do giảng viên quyết định.

## 3. Failure case

![Failure trên đối chứng nuScenes](../results/figures/fail_01_nusc_control_alarm.png)
- **Trường hợp:** nuScenes scene-0103_035, dữ liệu gốc, score 0,818900 > fallback 0,6: bị báo theo đối chứng âm dù tổng 34.720 điểm = reference, invalid 0%, empty bins 0.
- **Nguyên nhân:** ô [-100°,−90°) có 550/3.037 điểm, deficit 81,89% chi phối max; khác phân bố không đủ chứng minh dropout hay lỗi phần cứng. **Lớp debug: Metric.**
- **Phát hiện khi chạy thật:** log total_count, worst_bin và invalid; nếu score >0,6 nhưng total lệch <5%, invalid ≤0,5%, empty bins =0 thì chuyển sang review phân bố. Đây là đề xuất chưa benchmark, cần xác nhận bằng log sensor/chuỗi frame.
- **Failure thứ hai:** KITTI 000021, random dropout seed 42 làm 125.260 → 62.348 điểm (−50,23%) nhưng score 0,554524 ≤0,6 nên bị bỏ sót; Metric/ngưỡng quá lỏng. Ngưỡng 0,4 chọn ở CP3 bắt được frame này nhưng còn báo trên gốc 10%.
Chi tiết, ảnh `fail_02_*` và số liệu: [phân tích failure](EVIDENCE_DETAILS.md#3-failure-case), `results/health_failure_details.csv`; score tính lại từ raw points khớp CSV CP3, checksum và self-test PASS.

## 4. Khuyến nghị nếu triển khai thật

Use-case: QA log LiDAR của robot giao hàng trước khi gán nhãn; xếp frame để kỹ sư review, giữ dữ liệu gốc, chưa dùng score để phanh hoặc tự loại dữ liệu.
Với KITTI dùng ngưỡng review 0,4; nuScenes cần reference theo bối cảnh và kiểm tra trên scene mới. Ngưỡng thấp tăng tải review, cao bỏ sót dropout; worst_bin tốn p95 8,233 ms trên frame KITTI đã đo, nhưng chưa có latency toàn hệ thống.
Log frame/timestamp, sensor ID, finite_count, invalid_ratio, histogram, worst_bin, reference/version, score, ngưỡng và lý do; khi đối chiếu camera thêm time offset và ego-motion.
Quy tắc bổ trợ: invalid >0,5%, ô azimuth trống >0, time gap lệch quá ±20% so với expected; gap expected 0,5 s cho nuScenes, median timestamps cho synthetic, KITTI không có timestamp. Đây là cờ kiểm tra, không phải bằng chứng sensor hỏng.
Bước tiếp theo: kiểm tra nhóm ô liên tiếp, reference theo bối cảnh, xác nhận nhiều frame liên tục và đánh giá scene độc lập; đo cả I/O trước khi triển khai online.

## 5. Cách chạy lại

Từ gốc repo, PowerShell và Python 3.12; `requirements-lock.txt` ghi đúng phiên bản môi trường đã đo. Nếu đã có `.venv` thì bỏ lệnh tạo; trên Linux/macOS dùng `python3 -m venv .venv` và `source .venv/bin/activate`.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-lock.txt
python tools/verify_data.py --data-root data/kitti_mini
python tools/verify_data.py --data-root data/nuscenes_mini_subset
python -m src.test_projection
python -m starter.projection --data-root data/synthetic --frame 000000
python -m starter.projection --data-root data/kitti_mini --frame 000011
python -m starter.projection --data-root data/nuscenes_mini_subset --frame scene-0103_010
python -m starter.projection --data-root data/synthetic --frame 000000 --yaw-deg 2
python -m starter.data_health --data-root data/synthetic --out results/data_health.csv
python -m starter.data_health --data-root data/kitti_mini --out results/data_health_kitti.csv
python -m starter.data_health --data-root data/nuscenes_mini_subset --out results/data_health_nusc.csv
python -m src.data_health_dashboard
python -m src.exp_health_sweep
python -m src.plot_health_sweep
python -m src.analyze_health_failure
python -m src.compare_health_methods
python -m src.dataset_health_dashboard
python -m src.benchmark_health_latency --repeats 30
python tools/check_submission.py
```

**[B4]** Tool `src.exp_health_sweep` chạy mặc định được, mỗi tham số có help; `python -m src.exp_health_sweep --help` mô tả root, threshold, seed, output. Ví dụ đổi cấu hình: `python -m src.exp_health_sweep --data-roots data/kitti_mini --thresholds 0.2 0.4 0.6 --seed 42 --out-dir results/kitti_health` (không cần chạy để tái tạo báo cáo).
Tự nhận biết KITTI/nuScenes để dùng sector phía trước 0°/90°; input cần ≥2 frame và calibration có điểm hữu hạn. Ranking dựa trên score để review, chưa chứng minh chất lượng nhãn hay giá trị retrain.

Kiểm tra CP5: clone remote vào thư mục mới, áp dụng snapshot thay đổi cuối và tạo `.venv` riêng; cả 19 lệnh tái tạo/kiểm tra trên đều PASS. 16 CSV xác định và 12 PNG giống từng byte; timing được kiểm tra riêng, không yêu cầu giống thời gian đo.

## 6. Khai báo sử dụng AI

| Công cụ / nguồn | Dùng cho việc gì | Kiểm chứng đã thực hiện |
|---|---|---|
| Codex | Hỗ trợ setup, chọn topic/claim, viết hai hàm projection, test, dashboard, thí nghiệm, failure, bonus và biên tập REPORT. | Chạy checksum, điểm chuẩn/projection 3910/19946/3120; tính lại failure khớp CSV, xem ảnh; CP3/B1 rerun giống từng byte; kiểm tra warmup/120 latency rows và CLI; checker hình thức PASS; clone mới + venv riêng chạy đủ lệnh, 16 CSV và 12 PNG tái tạo giống từng byte. |
| Codelab và starter repo | Tham khảo self-test CP2, tái sử dụng reader, perturbation và point_stats; logic thí nghiệm E và so sánh do code trong src thực hiện. | Giữ nguyên data và mọi starter ngoài hai hàm được phép; cố định seed, reference từ calibration, báo claim bị bác bỏ và phạm vi timing. |

Học viên cần tự chạy lại, hiểu code và giải thích số liệu; không khai rằng học viên đã tự kiểm chứng nếu chưa thực hiện. Chi tiết số liệu, giới hạn và bonus ở [EVIDENCE_DETAILS.md](EVIDENCE_DETAILS.md).
