$(document).ready(function(){
    (function(){
        // CSS editor plugin

        var instances = {};

        $.fn.csseditor = function(){
            var self = this;

            var id = self.attr('id');

            if (instances[id]) {
                return instances[id];
            }
            instances[id] = self;

            self.addClass('csseditor');

            var style = $('style#preview-'+id);
            if (!style.size()){
                style = $('<style id="preview-'+id+'"></style>').appendTo('body');
            }

            var preview_link = $('<a class="preview-link" href="#">preview</a>')
                                .insertAfter(self);
            preview_link.click(function(){
                $('link#'+id+'-link').remove();
                style.html(self.val());
                return false;
            });

            return self;
        };
    })();

    $('#profile-form textarea').autosize();

    //$('#profile-form textarea#blogcss').csseditor();
    $('#profile-form textarea#usercss').csseditor();
});

