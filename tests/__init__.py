def destroy_tk_app(app):
    root_commands = set(app._tclCommands or ())
    for timer in app.tk.splitlist(app.tk.call("after", "info")):
        command = app.tk.splitlist(app.tk.call("after", "info", timer))[0]
        if command in root_commands:
            app.after_cancel(timer)
    app.destroy()