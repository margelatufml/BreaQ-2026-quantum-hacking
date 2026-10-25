## Level 1 (permutation matrices), 2000 shots per row

### N = 15 (12 qubits, t = 8 counting qubits)

| a | true r | recovered r | shots TV vs ideal | top outcomes y (count) | factors from this a |
|---|---|---|---|---|---|
| 2 | 4 | 4 | 0.010 | 128 (520), 64 (498), 0 (495), 192 (487) | 3 x 5 |
| 4 | 2 | 2 | 0.004 | 0 (1009), 128 (991) | 3 x 5 |
| 7 | 4 | 4 | 0.014 | 192 (525), 64 (503), 128 (491), 0 (481) | 3 x 5 |
| 8 | 4 | 4 | 0.012 | 192 (513), 128 (511), 0 (489), 64 (487) | 3 x 5 |
| 11 | 2 | 2 | 0.013 | 128 (1026), 0 (974) | 5 x 3 |
| 13 | 4 | 4 | 0.019 | 0 (519), 192 (518), 128 (488), 64 (475) | 3 x 5 |
| 14 | 2 | 2 | 0.001 | 0 (1003), 128 (997) | a^(r/2) = -1 mod N, retry with another a |

a with gcd(a, 15) > 1 (no circuit needed, the classical gcd step gives a factor): 3 (gcd 3), 5 (gcd 5), 6 (gcd 3), 9 (gcd 3), 10 (gcd 5), 12 (gcd 3)

### N = 21 (15 qubits, t = 10 counting qubits)

| a | true r | recovered r | shots TV vs ideal | top outcomes y (count) | factors from this a |
|---|---|---|---|---|---|
| 2 | 6 | 6 | 0.046 | 0 (331), 512 (320), 683 (245), 341 (237) | 7 x 3 |
| 4 | 3 | 3 | 0.043 | 0 (625), 683 (495), 341 (452), 682 (115) | r = 3 odd, retry with another a |
| 5 | 6 | 6 | 0.053 | 0 (329), 512 (307), 853 (263), 341 (238) | a^(r/2) = -1 mod N, retry with another a |
| 8 | 2 | 2 | 0.007 | 0 (1015), 512 (985) | 7 x 3 |
| 10 | 6 | 6 | 0.049 | 512 (368), 0 (320), 683 (228), 853 (224) | 3 x 7 |
| 11 | 6 | 6 | 0.045 | 0 (348), 512 (330), 683 (236), 171 (235) | 7 x 3 |
| 13 | 2 | 2 | 0.005 | 512 (1011), 0 (989) | 3 x 7 |
| 16 | 3 | 3 | 0.041 | 0 (683), 341 (476), 683 (437), 682 (124) | r = 3 odd, retry with another a |
| 17 | 6 | 6 | 0.039 | 512 (340), 0 (339), 683 (237), 171 (231) | a^(r/2) = -1 mod N, retry with another a |
| 19 | 6 | 6 | 0.073 | 512 (365), 0 (297), 853 (259), 341 (224) | 3 x 7 |
| 20 | 2 | 2 | 0.001 | 0 (1002), 512 (998) | a^(r/2) = -1 mod N, retry with another a |

a with gcd(a, 21) > 1 (no circuit needed, the classical gcd step gives a factor): 3 (gcd 3), 6 (gcd 3), 7 (gcd 7), 9 (gcd 3), 12 (gcd 3), 14 (gcd 7), 15 (gcd 3), 18 (gcd 3)

