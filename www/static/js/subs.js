$(document).ready(function(){
    $('.users .del').live('click', function(){
        if (!confirm($(this).attr('data-confirm'))) {
            return false;
        }
    });
});

