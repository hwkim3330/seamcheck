#!/bin/zsh
# 전 두루마리 순차 스캔. 결과는 all.jsonl 에 누적.
cd ~/seamcheck
for s in PHercParis4 PHerc1667 PHerc0814 PHerc1447 PHercMANBp PHerc0841 \
         PHerc1203 PHerc1451 PHercMAN5 PHerc0172 PHerc0332 PHerc0009B \
         PHerc0125 PHerc0139 PHerc0175A PHerc0175B PHerc0191 PHerc0211 \
         PHerc0257 PHerc0268 PHerc0306B PHerc0343 PHerc0343P PHerc0358 \
         PHerc0483A PHerc0483B PHerc0490A PHerc0490B PHerc0500P2 PHerc0800 \
         PHerc0813 PHerc0826 PHerc0846A PHerc0846B PHerc1218 PHerc1299 \
         PHerc1545 PHerc1667Cr1Fr3 PHerc51Cr4Fr8 PHercMANB PHercParis1Fr34 \
         PHercParis1Fr39 PHercParis2Fr143 PHercParis2Fr47 PHercParis3; do
  echo "=== $s ===" >> all.log
  ~/jev/.venv/bin/python seamcheck.py --s3 "$s" --json all --workers 8 >> all.log 2>&1
done
echo "ALLDONE" >> all.log
