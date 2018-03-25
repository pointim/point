$(document).ready(function(){
    // expand/collapse user info
    var aside = $('.aside');
    aside.addClass('collapsed');
    $('a#expand', aside).click(function(){
        if (aside.hasClass('collapsed')) {
            aside.removeClass('collapsed').addClass('expanded');
        } else {
            aside.removeClass('expanded').addClass('collapsed');
        }
    });

    // colourize tags
    var color_min = [160,160,160];
    var color_max = [53,88,124];
    var size_min = 1;
    var size_max = 1.2;

    var tag_links = $('#tags a');
    var tag_counts = tag_links.map(function(){
        return parseInt(this.getAttribute('data-cnt'), 10);
    }).sort(function(a,b){return a-b;});
    var cnt_min = tag_counts[0];
    var cnt_max = tag_counts[tag_counts.length-1];
    tag_links.each(function(){
        var cnt = parseInt(this.getAttribute('data-cnt'), 10);
        var r = Math.round((color_max[0]*cnt + color_min[0]*(tag_counts.length-cnt)) / tag_counts.length);
        var g = Math.round((color_max[1]*cnt + color_min[1]*(tag_counts.length-cnt)) / tag_counts.length);
        var b = Math.round((color_max[2]*cnt + color_min[2]*(tag_counts.length-cnt)) / tag_counts.length);
        $(this).css({'color': 'rgb('+r+','+g+','+b+')'});
    });
});

