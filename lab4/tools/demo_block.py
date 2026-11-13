import asyncio, time, statistics, math
S=0.19      # «обработка запроса» 1,9 с в масштабе 1:10
C=10; T=6.0
def pct(a,p): a=sorted(a); return a[math.ceil(p/100*len(a))-1]
async def run(kind):
    done=0; health=[]; stop=time.perf_counter()+T
    async def handler():
        if kind=="blocking": time.sleep(S)          # async def + requests/time.sleep
        else: await asyncio.sleep(S)                # async def + await
    async def client():
        nonlocal done
        while time.perf_counter()<stop:
            await handler(); done+=1
            await asyncio.sleep(0)      # между запросами цикл получает управление (сетевой ввод-вывод)
    async def health_poll():
        while time.perf_counter()<stop:
            t=time.perf_counter(); await asyncio.sleep(0.01)   # «ответ» /health
            health.append((time.perf_counter()-t-0.01)*1000); await asyncio.sleep(0.01)
    await asyncio.gather(*(client() for _ in range(C)),health_poll())
    return done/T, pct(health,95)
async def main():
    for k in ("blocking","await"):
        rps,h=await run(k); print(f"{k:9} C={C}: {rps:5.1f} запр/с (предел 1/S = {1/S:.1f} при блокировке; C/S = {C/S:.0f} без блокировки), задержка /health p95 ≈ {h:.0f} мс")
asyncio.run(main())
