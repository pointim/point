$(document).ready(function(){
    $('#top #forms').css({float: 'left', clear: 'both'}).height($('#top #login-form').outerHeight());
    // Toggle login/register form
    $('#top #login-link').click(function(){
        $('#top #register-form').fadeOut('fast', function(){
            $('#top #login-form').fadeIn();
            $('#top #login-form input[name="login"]').focus();
        });
        $('#top #forms').animate({height:$('#top #login-form').outerHeight()}, 'fast');
        return false;
    });
    $('#top #register-link').click(function(){
        $('#top #login-form').fadeOut('fast', function(){
            $('#top #register-form').fadeIn();
            $('#top #register-form input[name="login"]');
        });
        $('#top #forms').animate({height:$('#top #register-form').outerHeight()}, 'fast');
        return false;
    });

    // Show/hide password
    var password_input = $('#top #register-form #password-input');
    var show_password_input = $('#top #register-form #show-password-input');
    show_password_input.hide();
    $('#top #register-form #show-password-cb').removeAttr('checked')
     .click(function(){
        if ($(this).is(':checked')) {
            password_input.hide().removeAttr('name').removeAttr('required');
            show_password_input.val(password_input.val());
            show_password_input.attr('name', 'password')
                               .attr('required', 'required')
                               .show();
        } else {
            show_password_input.hide().removeAttr('name').removeAttr('required');
            password_input.val(show_password_input.val());
            password_input.attr('name', 'password')
                          .attr('required', 'required')
                          .show();
        }
    });

    // Check empty required fields
    $('#top #login-form, #top #register-form').submit(function(){
        var required = $('input[required]', $(this));
        var i;
        for (i=0; i<required.length; i++) {
            var r = $(required[i]);
            if (!r.val().trim() || r.hasClass('empty')) {
                r.addClass('error').focus();
                return false;
            }
        }
    });

    $('#top #login-form input, #top #register-form input').keypress(function(){
        $(this).removeClass('error');
    });

    // Placeholders for IE
    if ($.browser.msie) {
        $('input[placeholder]').each(function(){
            var input = $(this);

            input.focus(function(){
                if (input.hasClass('empty')) {
                    input.removeClass('empty').val('');
                }
            });

            input.blur(function(){
                if (!input.val()) {
                    input.addClass('empty').val(input.attr('placeholder'));
                }
            });

            if (!input.val()) {
                input.addClass('empty').val(input.attr('placeholder'));
            }
        });
    }
});
