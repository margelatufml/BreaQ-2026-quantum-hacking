## Level 2 (Beauregard QFT adders), 2000 shots per row

### N = 15 (18 qubits, t = 8 counting qubits)

| a | true r | recovered r | shots TV vs ideal | top outcomes y (count) | factors from this a |
|---|---|---|---|---|---|
| 2 | 4 | 4 | 0.013 | 64 (521), 192 (505), 128 (493), 0 (481) | 3 x 5 |
| 4 | 2 | 2 | 0.006 | 0 (1013), 128 (987) | 3 x 5 |
| 7 | 4 | 4 | 0.003 | 192 (506), 64 (499), 0 (498), 128 (497) | 3 x 5 |
| 8 | 4 | 4 | 0.013 | 192 (513), 0 (512), 64 (494), 128 (481) | 3 x 5 |
| 11 | 2 | 2 | 0.009 | 0 (1018), 128 (982) | 5 x 3 |
| 13 | 4 | 4 | 0.008 | 0 (512), 128 (503), 64 (493), 192 (492) | 3 x 5 |
| 14 | 2 | 2 | 0.005 | 0 (1010), 128 (990) | a^(r/2) = -1 mod N, retry with another a |

a with gcd(a, 15) > 1 (no circuit needed, the classical gcd step gives a factor): 3 (gcd 3), 5 (gcd 5), 6 (gcd 3), 9 (gcd 3), 10 (gcd 5), 12 (gcd 3)

### N = 21 (22 qubits, t = 10 counting qubits)

| a | true r | recovered r | shots TV vs ideal | top outcomes y (count) | factors from this a |
|---|---|---|---|---|---|
| 2 | 6 | 6 | 0.041 | 512 (337), 0 (329), 853 (240), 683 (233) | 7 x 3 |
| 4 | 3 | 3 | 0.033 | 0 (684), 683 (458), 341 (441), 682 (111) | r = 3 odd, retry with another a |
| 5 | 6 | 6 | 0.057 | 512 (358), 0 (304), 171 (233), 341 (229) | a^(r/2) = -1 mod N, retry with another a |
| 8 | 2 | 2 | 0.012 | 512 (1024), 0 (976) | 7 x 3 |
| 10 | 6 | 6 | 0.045 | 512 (353), 0 (345), 341 (228), 853 (225) | 3 x 7 |
| 11 | 6 | 6 | 0.049 | 512 (332), 0 (319), 683 (245), 853 (230) | 7 x 3 |
| 13 | 2 | 2 | 0.013 | 0 (1027), 512 (973) | 3 x 7 |
| 16 | 3 | 3 | 0.042 | 0 (706), 683 (462), 341 (416), 342 (118) | r = 3 odd, retry with another a |
| 17 | 6 | 6 | 0.055 | 0 (350), 512 (309), 171 (256), 341 (227) | a^(r/2) = -1 mod N, retry with another a |
| 19 | 6 | 6 | 0.042 | 512 (335), 0 (334), 171 (236), 683 (227) | 3 x 7 |
| 20 | 2 | 2 | 0.008 | 0 (1017), 512 (983) | a^(r/2) = -1 mod N, retry with another a |

a with gcd(a, 21) > 1 (no circuit needed, the classical gcd step gives a factor): 3 (gcd 3), 6 (gcd 3), 7 (gcd 7), 9 (gcd 3), 12 (gcd 3), 14 (gcd 7), 15 (gcd 3), 18 (gcd 3)

