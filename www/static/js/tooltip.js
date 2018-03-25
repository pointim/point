// Footnotes as Hovering Tooltips
//
// Original Scripts by Lukas Mathis and Osvaldas Valutis
//     - http://ignorethecode.net/blog/2010/04/20/footnotes/
//     - http://osvaldas.info/blog/elegant-css-and-jquery-tooltip- \
//           responsive-mobile-friendly/
// Modified by Syeong Gan
//     - Uses Mathis's base code and Valutis's tooltip design
//     - Searches for PHP Markdown Extra-style footnotes
//     - Disabled link click-through for Android devices
//
// Requirements: jQuery

$(document).ready(function() {
    Footnotes.initTooltip();
});

var Footnotes = {
    isIOS: function() {
        var agent = navigator.userAgent.toLowerCase();
        return(
            agent.indexOf('iphone') >= 0 ||
            agent.indexOf('ipad') >= 0 ||
            agent.indexOf('ipod') >= 0
        );
    },
    isAndroid: function() {
        var agent = navigator.userAgent.toLowerCase();
        return(agent.indexOf('android') >= 0);
    },
    initTooltip: function() {
        var targets = $('[rel~=footnote]');
        
        // Load Tooltip CSS
        //$('body').append('<style>' + cssTooltip + '</style>');
        
        targets.unbind('mouseover', Footnotes.addTooltip);
        targets.unbind('mouseout', Footnotes.removeTooltip);
        
        targets.bind('mouseover', Footnotes.addTooltip);
        targets.bind('mouseout', Footnotes.removeTooltip);
    },
    addTooltip: function () {
        $('#tooltip').stop();
        $('#tooltip').remove();
        
        // Find matching footnote text and remove extraneous tags
        var target = $(this);
        var id = target.attr('href').substr(1);
        var fn = document.getElementById(id);
        var tip = $(fn).html();
        tip = tip.replace(/<p>(.+)<a href="#fnref.+<\/a><\/p>/, "$1");
        if( !tip || tip == '' ) return false;
        
        // Create Tooltip
        var tooltip = $('<div id="tooltip"></div>');
        
        // Check for mobile devices
        if(Footnotes.isIOS()) {
            tooltip.bind('click', Footnotes.removeTooltip);
        } else if(Footnotes.isAndroid()) {
            tooltip.bind('click', Footnotes.removeTooltip);
            target.click(function(e) { e.preventDefault(); });
        } else {
            tooltip.bind('mouseover', Footnotes.hoverTooltip);
            tooltip.bind('mouseout', Footnotes.removeTooltip);
        }
        
        // Add Tooltip to page (hidden)
        tooltip.css('opacity', 0)
               .html(tip)
               .appendTo('body');
        
        var positionTooltip = function() {
            // Determine size of tooltip (max width of 340px)
            if($(window).width() < 640)
                tooltip.css('max-width', $(window).width() / 2);
            else
                tooltip.css('max-width', 340);
            
            // Set initial position of tooltip
            var pos_left = target.offset().left + (target.outerWidth() / 2) - (tooltip.outerWidth() / 2),
                pos_top  = target.offset().top - tooltip.outerHeight() - 30;
            
            // Check if the left side of the tooltip is off screen
            if(pos_left < 0) {
                pos_left = target.offset().left + (target.outerWidth() / 2) - 20;
                tooltip.addClass('left');
            } else
                tooltip.removeClass('left');
            
            // Check if the right side of the tooltip is off screen
            if(pos_left + tooltip.outerWidth() > $(window).width()) {
                pos_left = target.offset().left - tooltip.outerWidth() + (target.outerWidth() / 2) + 20;
                tooltip.addClass('right');
            } else
                tooltip.removeClass('right');
            
            // Check if the ltop of the tooltip is off screen
            if(pos_top < 0) {
                var pos_top = target.offset().top + target.outerHeight();
                tooltip.addClass('top');
            } else
                tooltip.removeClass('top');
            
            tooltip.css({ left: pos_left, top: pos_top })
                   .animate({ top: '+=10', opacity: 1 }, 100);
        }
        
        // Show Tooltip (and reposition if window changes)
        positionTooltip();
        $(window).resize(positionTooltip());
    },
    removeTooltip: function() {
        var tooltip = $('#tooltip');
        
        tooltip.animate({ top: '-=10', opacity: 0 }, 100, function() {
                tooltip.remove();
        });
    },
    hoverTooltip: function() {
        var tooltip = $('#tooltip');
        
        tooltip.stop();
        tooltip.css('opacity', 1);
    }
}