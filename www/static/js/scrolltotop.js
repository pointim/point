window.addEventListener("load", function(){
    var fuckingButton = document.getElementById("scrollToTop"),
        hideFuckingButtonTimeout = 3000,
        scrollStarted;

    var scrollStartedFunction = function () {
        if (undefined != scrollStarted) clearTimeout(scrollStarted);

        $(fuckingButton).removeClass("totophidden")
                        .addClass("totopshowed");
        setTimeout(function(){
            $(fuckingButton).removeClass("totophide")
                            .addClass("totopshow");
        }, 5);
        scrollStarted = setTimeout(function(){
            $(fuckingButton).removeClass("totopshow")
                            .addClass("totophide");
            clearTimeout(scrollStarted);
            setTimeout(function(){
                $(fuckingButton).removeClass("totopshowed")
                                .addClass("totophidden");
            }, 5);
        }, hideFuckingButtonTimeout);
    };

    window.addEventListener("scroll", scrollStartedFunction);
});