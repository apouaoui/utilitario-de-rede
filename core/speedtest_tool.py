def run_speedtest(progress_callback=None):
    import speedtest

    st = speedtest.Speedtest()
    if progress_callback:
        progress_callback("Selecionando melhor servidor...")
    st.get_best_server()
    if progress_callback:
        progress_callback("Testando download...")
    download = st.download()
    if progress_callback:
        progress_callback("Testando upload...")
    upload = st.upload()
    result = st.results.dict()
    return {
        "download_mbps": download / 1_000_000,
        "upload_mbps": upload / 1_000_000,
        "ping_ms": result.get("ping"),
        "server": result.get("server", {}).get("sponsor", ""),
        "isp": result.get("client", {}).get("isp", ""),
    }
