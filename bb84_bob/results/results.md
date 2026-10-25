# Results (simulated Alice, N = 200000, 30 trials per cell, eps = eps_PA = 1e-10, Cascade 'backtrack' unless noted)

## 1. Final key length l (bits, mean over non-aborted runs) and abort rate

Cell = mean l / abort rate. Same random seeds for both bounds. 'noise' = qber of the channel, 'Eve' = intercept-resend fraction.

| noise | Eve | bound | k=10000 | k=20000 | k=30000 |
|---|---|---|---|---|---|
| 1% | 0% | cp | 70339 (sd 668) / 0% | 63720 (sd 448) / 0% | 56190 (sd 360) / 0% |
| 1% | 0% | hoeffding | 58553 (sd 447) / 0% | 55705 (sd 348) / 0% | 50244 (sd 301) / 0% |
| 1% | 1% | cp | 67195 (sd 809) / 0% | 60967 (sd 507) / 0% | 53789 (sd 369) / 0% |
| 1% | 1% | hoeffding | 56038 (sd 547) / 0% | 53402 (sd 391) / 0% | 48187 (sd 306) / 0% |
| 2% | 0% | cp | 58305 (sd 824) / 0% | 53068 (sd 483) / 0% | 46937 (sd 400) / 0% |
| 2% | 0% | hoeffding | 48684 (sd 594) / 0% | 46604 (sd 397) / 0% | 42164 (sd 343) / 0% |
| 2% | 1% | cp | 55731 (sd 867) / 0% | 50812 (sd 495) / 0% | 44962 (sd 376) / 0% |
| 2% | 1% | hoeffding | 46505 (sd 629) / 0% | 44621 (sd 406) / 0% | 40397 (sd 325) / 0% |
| 3% | 0% | cp | 47822 (sd 731) / 0% | 43859 (sd 489) / 0% | 38908 (sd 364) / 0% |
| 3% | 0% | hoeffding | 39697 (sd 568) / 0% | 38412 (sd 417) / 0% | 34897 (sd 324) / 0% |
| 3% | 1% | cp | 45559 (sd 831) / 0% | 41864 (sd 523) / 0% | 37167 (sd 388) / 0% |
| 3% | 1% | hoeffding | 37716 (sd 648) / 0% | 36611 (sd 449) / 0% | 33302 (sd 347) / 0% |
| 4% | 0% | cp | 38429 (sd 891) / 0% | 35571 (sd 563) / 0% | 31664 (sd 411) / 0% |
| 4% | 0% | hoeffding | 31421 (sd 715) / 0% | 30881 (sd 493) / 0% | 28215 (sd 374) / 0% |
| 4% | 1% | cp | 36420 (sd 922) / 0% | 33789 (sd 556) / 0% | 30123 (sd 416) / 0% |
| 4% | 1% | hoeffding | 29630 (sd 745) / 0% | 29247 (sd 487) / 0% | 26784 (sd 378) / 0% |

## 2. Abort rate versus noise (k = 20000, Eve 0)

'Step 8' = Q_u > 11%; 'l<=0' = Q_u below 11% but the key length formula gives no key; 'key < msg' = 0 < l but the key is shorter than the 8*len(message) bits the one-time pad needs (abort at step 15). The three reasons add up to the abort rate.

| noise | bound | abort rate | of which step 8 | of which l<=0 | of which key < msg | mean Q_hat | mean l (non-aborted) |
|---|---|---|---|---|---|---|---|
| 5.0% | cp | 0% | 0% | 0% | 0% | 0.0503 | 27961 |
| 5.0% | hoeffding | 0% | 0% | 0% | 0% | 0.0503 | 23862 |
| 6.0% | cp | 0% | 0% | 0% | 0% | 0.0603 | 20711 |
| 6.0% | hoeffding | 0% | 0% | 0% | 0% | 0.0603 | 17100 |
| 7.0% | cp | 0% | 0% | 0% | 0% | 0.0702 | 14046 |
| 7.0% | hoeffding | 0% | 0% | 0% | 0% | 0.0702 | 10839 |
| 8.0% | cp | 0% | 0% | 0% | 0% | 0.0802 | 7761 |
| 8.0% | hoeffding | 0% | 0% | 0% | 0% | 0.0802 | 4905 |
| 9.0% | cp | 0% | 0% | 0% | 0% | 0.0902 | 1930 |
| 9.0% | hoeffding | 100% | 100% | 0% | 0% | 0.0902 | nan |
| 9.5% | cp | 97% | 23% | 70% | 3% | 0.0953 | 415 |
| 9.5% | hoeffding | 100% | 100% | 0% | 0% | 0.0953 | nan |
| 10.0% | cp | 100% | 100% | 0% | 0% | 0.1004 | nan |
| 10.0% | hoeffding | 100% | 100% | 0% | 0% | 0.1004 | nan |
| 11.0% | cp | 100% | 100% | 0% | 0% | 0.1104 | nan |
| 11.0% | hoeffding | 100% | 100% | 0% | 0% | 0.1104 | nan |

## 3. Cascade variants (k = 20000, Eve 0.5%, CP)

'brief' = steps 9-11 literally (3 passes, equal blocks b = 0.73/Q_hat, no back-tracking); 'backtrack' = 3 passes, blocks b, 3b, 9b with back-tracking (default); 'backtrack_2x' = b, 2b, 4b. Leak = parity bits of the successful run set (all attempts).

| noise | Cascade | mean attempts | mean parity bits | mean l | leak / (n h(Q_hat)) |
|---|---|---|---|---|---|
| 1% | brief | 1.97 | 12809 | 57211 | 1.79 |
| 1% | backtrack_2x | 1.00 | 7951 | 62107 | 1.11 |
| 1% | backtrack | 1.00 | 7726 | 62332 | 1.08 |
| 2% | brief | 2.00 | 22834 | 42022 | 1.91 |
| 2% | backtrack_2x | 1.00 | 13403 | 51493 | 1.12 |
| 2% | backtrack | 1.00 | 12965 | 51931 | 1.08 |
| 3% | brief | 2.00 | 32259 | 28224 | 2.00 |
| 3% | backtrack_2x | 1.00 | 18378 | 42145 | 1.14 |
| 3% | backtrack | 1.00 | 17653 | 42870 | 1.09 |
| 4% | brief | 2.00 | 41028 | 15547 | 2.06 |
| 4% | backtrack_2x | 1.00 | 22810 | 33805 | 1.14 |
| 4% | backtrack | 1.00 | 21921 | 34693 | 1.10 |

## 4. Which k maximises the final key? (Eve 0.5%)

Empirical = mean l over trials (sd of the mean about 1/sqrt(trials) of the sd in table 1). Analytic = expected l with m = Q k, f_EC measured in the runs of table 1 (CP f_EC, Hoeffding f_EC).

| noise | bound | k=3000 | k=5000 | k=7500 | k=10000 | k=15000 | k=20000 | k=30000 | best empirical k | best empirical k in 10000-30000 | best analytic k |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1% | cp | 69212 | 70339 | 69829 | 68749 | 65740 | 62332 | 54982 | 5000 | 10000 | 5750 (l = 70305) |
| 1% | hoeffding | 50736 | 54885 | 56767 | 57288 | 56477 | 54547 | 49217 | 10000 | 10000 | 10500 (l = 57287) |
| 2% | cp | 56363 | 57814 | 57662 | 57012 | 54671 | 51931 | 45932 | 5000 | 10000 | 6250 (l = 57796) |
| 2% | hoeffding | 40993 | 45015 | 46906 | 47590 | 47105 | 45604 | 41266 | 10000 | 10000 | 11500 (l = 47568) |
| 3% | cp | 45122 | 46972 | 47102 | 46688 | 44983 | 42870 | 38029 | 7500 | 10000 | 7500 (l = 47050) |
| 3% | hoeffding | 32013 | 36039 | 37948 | 38703 | 38579 | 37519 | 34092 | 10000 | 10000 | 11750 (l = 38813) |
| 4% | cp | 35082 | 37099 | 37571 | 37445 | 36313 | 34693 | 30901 | 7500 | 10000 | 8000 (l = 37544) |
| 4% | hoeffding | 23799 | 27647 | 29651 | 30543 | 30774 | 30076 | 27508 | 15000 | 15000 | 13750 (l = 30806) |

Runs: 3960; runs that finished without abort but whose message did not decrypt correctly: 0. Wall time 505 s.
