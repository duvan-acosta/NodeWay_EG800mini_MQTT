try:
    from usr import app_main

    app_main.main()
except Exception as e:
    try:
        import log

        log.basicConfig(level=log.ERROR)
        logger = log.getLogger("BOOT")
        logger.error("app_main boot error: {}".format(e))
    except:
        print("app_main boot error:", e)
    raise
